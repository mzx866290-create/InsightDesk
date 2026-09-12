"""
文档处理与向量化管道
支持 PDF、Word、Markdown、CSV 等格式的文档加载、分块、向量化和检索
"""

import logging
import math
import os
import shutil
import sys
from typing import Any, List, Optional, cast
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from dotenv import load_dotenv

try:  # local-inference stack; slim distributions may ship without it
    from langchain_huggingface import HuggingFaceEmbeddings
    from sentence_transformers import CrossEncoder

    LOCAL_INFERENCE_AVAILABLE: bool = (
        HuggingFaceEmbeddings is not None and CrossEncoder is not None
    )
except Exception:  # pragma: no cover - exercised by slim distributions
    HuggingFaceEmbeddings = None  # type: ignore
    CrossEncoder = None  # type: ignore
    LOCAL_INFERENCE_AVAILABLE = False
from backend.stores.vector_store import create_vector_store_adapter
from backend.core.storage_runtime import (
    VECTOR_STORE_PROVIDER_FAISS,
    vector_store_runtime_summary,
)
from backend.doc_governance_helpers import (
    apply_document_governance_metadata,
    apply_topic_version_status,
    content_hash,
    dedupe_index_documents,
    document_governance_boost,
    extract_date_candidates,
    extract_expiry_timestamp,
    extract_version_label,
    extract_version_number,
    governance_rank,
    normalize_source_key,
    normalize_topic_key,
    parse_date_parts,
    prepare_documents_for_index,
)

load_dotenv()


logger = logging.getLogger(__name__)

from backend.doc_pipeline_governance import DocPipelineGovernanceMixin
from backend.doc_pipeline_loaders import DocPipelineLoadersMixin
from backend.doc_pipeline_retrieval import DocPipelineRetrievalMixin
from backend.doc_pipeline_store import DocPipelineStoreMixin

from backend.doc_pipeline_constants import (  # noqa: F401
    KEYWORD_TOKEN_PATTERN,
    VERSION_TOKEN_PATTERN,
    DATE_TOKEN_PATTERN,
    COMPACT_DATE_TOKEN_PATTERN,
    EXPIRY_HINT_PATTERN,
)

if sys.platform == "win32":
    try:
        reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_stdout):
            reconfigure_stdout(encoding="utf-8")
    except Exception:
        pass



class DocPipeline(
    DocPipelineGovernanceMixin,
    DocPipelineStoreMixin,
    DocPipelineLoadersMixin,
    DocPipelineRetrievalMixin,
):
    _embedding_cache: dict[tuple[str, str], Any] = {}
    _reranker_cache: dict[tuple[str, str], Any] = {}
    _reranker: Any | None
    """文档处理管道类"""
    """文档处理管道类"""

    def __init__(
        self,
        embedding_model: Optional[str] = None,
        device: Optional[str] = None,
        vector_store_path: Optional[str] = None,
    ):
        """
        初始化文档处理管道

        Args:
            embedding_model: Embedding 模型名称
            device: 计算设备 (cpu/cuda)
            vector_store_path: 向量库持久化路径
        """
        self.embedding_model = embedding_model or os.getenv(
            "EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5"
        )
        self.device = self._resolve_device(device)
        self.vector_store_path: str = str(vector_store_path or os.getenv(
            "VECTOR_STORE_PATH", "./vector_store"
        ))
        self.vector_store_adapter = create_vector_store_adapter(path=self.vector_store_path)

        # 延迟加载: 首次使用时才加载模型,避免启动卡顿
        self._embeddings: Any | None = None
        self._reranker = None  # 延迟加载 Reranker 模型
        self._reranker_device = self.device

        # 普通文档用 800 字符切分，平衡信息密度和检索精准度
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", "。", "；", "!", "?", " ", ""],
            length_function=len,
        )
        # 简历/结构化文档常见章节标题关键词
        self._resume_section_keywords = (
            "工作经历", "工作经验", "项目经历", "项目经验",
            "项目介绍", "项目职责", "项目结果",
            "教育背景", "教育经历", "教育信息", "学历",
            "技能", "专业技能", "核心技能", "技术能力",
            "技能证书",
            "自我评价", "个人介绍", "个人简介", "求职意向",
            "荣誉", "证书", "资质", "培训经历",
            "实习经历", "社会实践", "兴趣爱好",
        )
        self._resume_detect_keywords = (
            "工作经历", "工作经验", "项目经历", "求职意向",
            "教育背景", "应聘", "毕业院校", "专业技能",
            "项目介绍", "项目职责", "项目结果", "技能证书", "自我评价",
            "履历", "简历",
        )

        self.vectorstore: Optional[Any] = None

    def _resolve_device(self, device: Optional[str]) -> str:
        """优先使用显卡；若不可用则回退到 CPU。"""
        configured = device or os.getenv("EMBEDDING_DEVICE")
        if configured:
            normalized = configured.strip().lower()
            if normalized.startswith("cuda"):
                try:
                    import torch

                    if torch.cuda.is_available():
                        return configured
                    logger.warning(
                        "EMBEDDING_DEVICE=%s，但当前 PyTorch/CUDA 不可用，自动回退到 CPU",
                        configured,
                    )
                    return "cpu"
                except Exception:
                    logger.warning(
                        "检测 CUDA 可用性失败，EMBEDDING_DEVICE=%s 自动回退到 CPU",
                        configured,
                        exc_info=True,
                    )
                    return "cpu"
            return configured

        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            logger.debug("torch/cuda 检测失败，回退到 CPU", exc_info=True)

        return "cpu"

    @property
    def embeddings(self):
        """延迟加载 Embedding 模型"""
        if HuggingFaceEmbeddings is None:
            raise RuntimeError(
                "本地嵌入依赖未安装（sentence-transformers/langchain-huggingface）。"
                "请安装完整依赖或改用云端 embedding。"
            )
        if self._embeddings is None:
            cache_key = (self.embedding_model, self.device)
            cached = self._embedding_cache.get(cache_key)
            if cached is not None:
                self._embeddings = cached
                return self._embeddings

            logger.info(
                "加载 Embedding 模型: %s (设备: %s)", self.embedding_model, self.device
            )
            try:
                self._embeddings = HuggingFaceEmbeddings(
                    model_name=self.embedding_model,
                    model_kwargs={"device": self.device},
                    encode_kwargs={"normalize_embeddings": True},
                )
            except Exception as exc:
                lower = str(exc).lower()
                can_retry_on_cpu = self.device != "cpu" and any(
                    token in lower
                    for token in (
                        "cuda",
                        "out of memory",
                        "torch not compiled with cuda enabled",
                    )
                )
                if not can_retry_on_cpu:
                    raise

                logger.warning(
                    "Embedding 模型在设备 %s 上加载失败，自动回退到 CPU: %s",
                    self.device,
                    exc,
                )
                self.device = "cpu"
                self._embeddings = HuggingFaceEmbeddings(
                    model_name=self.embedding_model,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
                cache_key = (self.embedding_model, self.device)
            logger.info("Embedding 模型加载完成")
            self._embedding_cache[cache_key] = self._embeddings
        return self._embeddings

    @property
    def reranker(self):
        """延迟加载 Reranker 模型 (用于二段重排)"""
        if self._reranker is None:
            reranker_model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
            self._reranker, self._reranker_device = self._load_reranker(
                reranker_model,
                preferred_device=self._reranker_device or self.device,
            )
        return self._reranker

    def _should_retry_reranker_on_cpu(self, exc: Exception, device: str) -> bool:
        if str(device or "").lower() == "cpu":
            return False
        lower = str(exc).lower()
        return any(
            token in lower
            for token in (
                "cuda",
                "cublas",
                "out of memory",
                "torch not compiled with cuda enabled",
                "device-side assert",
                "not enough memory",
            )
        )

    def _create_reranker(
        self,
        model_name: str,
        device: str,
        *,
        local_files_only: bool,
    ) -> Any:
        if CrossEncoder is None:
            raise RuntimeError(
                "本地重排依赖未安装（sentence-transformers）。请安装完整依赖或关闭重排。"
            )
        hf_token = os.getenv("HF_TOKEN") or None
        return cast(
            CrossEncoder,
            CrossEncoder(
                model_name,
                max_length=512,
                device=device,
                local_files_only=local_files_only,
                token=hf_token,
            ),
        )

    def _load_reranker(
        self,
        model_name: str,
        preferred_device: str,
    ) -> tuple[Any, str]:
        candidate_devices = [str(preferred_device or self.device or "cpu").strip() or "cpu"]
        if candidate_devices[0].lower() != "cpu":
            candidate_devices.append("cpu")

        last_error: Exception | None = None
        for device in candidate_devices:
            cache_key = (model_name, device)
            cached = self._reranker_cache.get(cache_key)
            if cached is not None:
                logger.info("复用已缓存 Reranker: %s (device=%s)", model_name, device)
                return cached, device

            logger.info("加载 Reranker 模型: %s (device=%s)", model_name, device)
            try:
                reranker = self._create_reranker(
                    model_name,
                    device,
                    local_files_only=True,
                )
            except Exception:
                logger.warning(
                    "本地缓存未命中，回退到常规方式加载 Reranker: %s (device=%s)",
                    model_name,
                    device,
                    exc_info=True,
                )
                try:
                    reranker = self._create_reranker(
                        model_name,
                        device,
                        local_files_only=False,
                    )
                except Exception as remote_exc:
                    last_error = remote_exc
                    if self._should_retry_reranker_on_cpu(remote_exc, device):
                        logger.warning(
                            "Reranker 在 %s 上加载失败，自动回退到 CPU: %s",
                            device,
                            remote_exc,
                        )
                        continue
                    raise

            self._reranker_cache[cache_key] = reranker
            logger.info("Reranker 模型加载完成 (device=%s)", device)
            return reranker, device

        if last_error is not None:
            raise last_error
        raise RuntimeError("Failed to load reranker model")

    def _predict_rerank_scores(self, query: str, candidates: List[Document]) -> List[float]:
        pairs = [[query, doc.page_content] for doc in candidates]
        if not pairs:
            return []

        reranker_model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
        try:
            raw_scores = self.reranker.predict(pairs)
        except Exception as exc:
            if self._should_retry_reranker_on_cpu(exc, self._reranker_device):
                logger.warning(
                    "Reranker 预测在 %s 上失败，自动回退到 CPU: %s",
                    self._reranker_device,
                    exc,
                )
                self._reranker = None
                self._reranker_device = "cpu"
                self._reranker, self._reranker_device = self._load_reranker(
                    reranker_model,
                    preferred_device="cpu",
                )
                raw_scores = self.reranker.predict(pairs)
            else:
                raise

        return self._normalize_rerank_scores(raw_scores, expected=len(candidates))

    def _normalize_rerank_scores(self, raw_scores: Any, expected: int) -> List[float]:
        if hasattr(raw_scores, "tolist"):
            raw_scores = raw_scores.tolist()
        elif hasattr(raw_scores, "__iter__") and not isinstance(
            raw_scores,
            (str, bytes, list, tuple),
        ):
            raw_scores = list(raw_scores)

        if isinstance(raw_scores, (int, float)):
            raw_scores = [raw_scores]
        elif not isinstance(raw_scores, (list, tuple)):
            raw_scores = []

        normalized: List[float] = []
        for value in raw_scores:
            scalar = value
            if isinstance(value, (list, tuple)):
                scalar = value[0] if value else 0.0
            try:
                score = float(scalar)
            except (TypeError, ValueError):
                score = 0.0
            if not math.isfinite(score):
                score = 0.0
            normalized.append(score)

        if expected > 0 and len(normalized) < expected:
            normalized.extend([0.0] * (expected - len(normalized)))

        return normalized[:expected] if expected > 0 else normalized


    def get_stats(self) -> dict:
        """
        获取向量库统计信息

        Returns:
            统计信息字典
        """
        validation = self.storage_validation_summary()
        if self.vectorstore is None:
            return {
                "status": "未初始化",
                "total_docs": 0,
                "store_path": self.vector_store_path,
                "vector_store_provider": self.vector_store_adapter.provider,
                "storage_validation": validation,
            }

        total_docs = 0
        index = getattr(self.vectorstore, "index", None)
        if index is not None:
            total_docs = int(getattr(index, "ntotal", 0) or 0)
        else:
            try:
                total_docs = len(self._all_index_documents())
            except Exception:
                total_docs = 0

        return {
            "status": "已加载",
            "total_docs": total_docs,
            "store_path": self.vector_store_path,
            "vector_store_provider": self.vector_store_adapter.provider,
            "storage_validation": validation,
        }

    def storage_validation_summary(self) -> dict[str, Any]:
        """Return a side-effect-free vector-store validation payload."""

        summary_factory = getattr(self.vector_store_adapter, "validation_summary", None)
        if callable(summary_factory):
            return dict(summary_factory(path=self.vector_store_path))
        return vector_store_runtime_summary(
            provider=getattr(self.vector_store_adapter, "provider", None),
            path=self.vector_store_path,
        )

    def delete_store(self) -> bool:
        """
        删除向量库磁盘文件并重置内存状态

        Returns:
            是否删除成功
        """

        self.vectorstore = None
        if self.vector_store_adapter.provider != VECTOR_STORE_PROVIDER_FAISS:
            delete_store = getattr(self.vector_store_adapter, "delete", None)
            if delete_store is None:
                logger.info(
                    "Vector store provider %s does not expose delete().",
                    self.vector_store_adapter.provider,
                )
                return False
            try:
                deleted = bool(delete_store(path=self.vector_store_path))
            except Exception as e:
                logger.error(
                    "Vector store provider %s delete failed: %s",
                    self.vector_store_adapter.provider,
                    e,
                )
                return False
            logger.info(
                "Vector store provider %s delete result: %s",
                self.vector_store_adapter.provider,
                deleted,
            )
            return deleted
        if not os.path.exists(self.vector_store_path):
            return False
        try:
            shutil.rmtree(self.vector_store_path)
            logger.info("向量库已删除: %s", self.vector_store_path)
            return True
        except Exception as e:
            logger.error("向量库删除失败: %s", e)
            return False


for _name, _impl in {
    "_normalize_source_key": normalize_source_key,
    "_normalize_topic_key": normalize_topic_key,
    "_parse_date_parts": parse_date_parts,
    "_extract_date_candidates": extract_date_candidates,
    "_extract_expiry_timestamp": extract_expiry_timestamp,
    "_extract_version_number": extract_version_number,
    "_extract_version_label": extract_version_label,
    "_content_hash": content_hash,
    "_governance_rank": governance_rank,
    "_apply_document_governance_metadata": apply_document_governance_metadata,
    "_dedupe_index_documents": dedupe_index_documents,
    "_apply_topic_version_status": apply_topic_version_status,
    "_prepare_documents_for_index": prepare_documents_for_index,
    "_document_governance_boost": document_governance_boost,
}.items():
    setattr(DocPipeline, _name, staticmethod(cast(Any, _impl)))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
    )
    pipeline = DocPipeline()

    test_files = ["test.pdf", "test.docx", "test.md"]
    existing_files = [f for f in test_files if os.path.exists(f)]

    if existing_files:
        count = pipeline.ingest(existing_files)
        logger.info("导入完成: %d 个文档片段", count)

        results = pipeline.search("测试查询", k=3)
        logger.info("检索结果 (%d 条):", len(results))
        for i, doc in enumerate(results, 1):
            logger.info(
                "%d. %s: %s...",
                i,
                doc.metadata.get("source", "未知"),
                doc.page_content[:100],
            )
    else:
        logger.warning("未找到测试文件,请先创建 test.pdf/test.docx/test.md")
