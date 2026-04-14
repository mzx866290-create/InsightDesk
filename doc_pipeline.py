"""
文档处理与向量化管道
支持 PDF、Word、Markdown、CSV 等格式的文档加载、分块、向量化和检索
"""

import logging
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, List, Optional
import pandas as pd
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    CSVLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 设置标准输出为 UTF-8，避免 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class DocPipeline:
    _embedding_cache = {}
    _reranker_cache = {}
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
        self.vector_store_path = vector_store_path or os.getenv(
            "VECTOR_STORE_PATH", "./vector_store"
        )

        # 延迟加载: 首次使用时才加载模型,避免启动卡顿
        self._embeddings = None
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

        self.vectorstore: Optional[FAISS] = None

    @staticmethod
    def _path_has_non_ascii(path: str) -> bool:
        try:
            path.encode("ascii")
            return False
        except UnicodeEncodeError:
            return True

    def _should_use_faiss_staging_dir(self) -> bool:
        resolved = str(Path(self.vector_store_path).resolve())
        return sys.platform == "win32" and self._path_has_non_ascii(resolved)

    def _make_faiss_staging_dir(self, prefix: str) -> Path:
        base_dir = Path(tempfile.gettempdir()) / "ai_kb_faiss"
        base_dir.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=f"{prefix}_", dir=str(base_dir)))

    def _save_vectorstore_local(self) -> None:
        target_dir = Path(self.vector_store_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        if not self._should_use_faiss_staging_dir():
            self.vectorstore.save_local(str(target_dir))
            return

        staging_dir = self._make_faiss_staging_dir("save")
        logger.info(
            "FAISS save workaround enabled for Windows non-ASCII path: %s",
            target_dir,
        )
        try:
            self.vectorstore.save_local(str(staging_dir))
            for file_name in ("index.faiss", "index.pkl"):
                shutil.copy2(staging_dir / file_name, target_dir / file_name)
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def _load_vectorstore_local(self) -> FAISS:
        target_dir = Path(self.vector_store_path)
        if not self._should_use_faiss_staging_dir():
            return FAISS.load_local(
                str(target_dir),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )

        staging_dir = self._make_faiss_staging_dir("load")
        logger.info(
            "FAISS load workaround enabled for Windows non-ASCII path: %s",
            target_dir,
        )
        try:
            for file_name in ("index.faiss", "index.pkl"):
                shutil.copy2(target_dir / file_name, staging_dir / file_name)
            return FAISS.load_local(
                str(staging_dir),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

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
    ) -> CrossEncoder:
        hf_token = os.getenv("HF_TOKEN") or None
        return CrossEncoder(
            model_name,
            max_length=512,
            device=device,
            local_files_only=local_files_only,
            token=hf_token,
        )

    def _load_reranker(
        self,
        model_name: str,
        preferred_device: str,
    ) -> tuple[CrossEncoder, str]:
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

    def _is_resume_doc(self, text: str) -> bool:
        """判断文本是否为简历类文档（命中 2 个及以上关键词则认定）"""
        count = sum(1 for kw in self._resume_detect_keywords if kw in text)
        return count >= 2

    def _smart_split(self, docs: List[Document]) -> List[Document]:
        """
        智能分块：简历/结构化文档按语义章节切分，普通文档使用标准切分器（800字）。
        简历中每个章节作为一个独立 chunk，保证检索时能拿到完整的工作/项目/教育信息。
        """
        import re as _re

        result: List[Document] = []
        for doc in docs:
            text = doc.page_content
            source = doc.metadata.get("source", "未知")
            # 判断是否为简历类文档
            if not self._is_resume_doc(text):
                before = len(result)
                result.extend(self.splitter.split_documents([doc]))
                logger.debug(
                    "[SmartSplit] 普通文档 %s → %d 个 chunk（chunk_size=800）",
                    source,
                    len(result) - before,
                )
                continue

            # 简历文档：按章节标题分段
            section_keywords = sorted(
                self._resume_section_keywords, key=len, reverse=True
            )
            kw_pattern = "|".join(_re.escape(kw) for kw in section_keywords)
            heading_section_re = _re.compile(
                r"(?:^|\n)\s*(?:#+\s*|【|■|▶|◆|●|○|·)?(?P<section>"
                + kw_pattern
                + r")[\s：:：\】]*",
                _re.MULTILINE,
            )
            positions = [m.start("section") for m in heading_section_re.finditer(text)]

            # mammoth 可能把标题和正文揉到同一行，此时退化为全文关键词切分
            if len(positions) < 2:
                relaxed_keywords = [kw for kw in section_keywords if len(kw) >= 4]
                relaxed_kw_pattern = "|".join(
                    _re.escape(kw) for kw in relaxed_keywords
                )
                relaxed_section_re = _re.compile(
                    r"(?:^|\n|[ \t]{2,}|[。；;!?！？])\s*(?:#+\s*|【|■|▶|◆|●|○|·)?(?P<section>"
                    + relaxed_kw_pattern
                    + r")[\s：:：\】]*",
                    _re.MULTILINE,
                )
                positions = []
                last_pos = -1
                for match in relaxed_section_re.finditer(text):
                    pos = match.start("section")
                    if pos - last_pos < 6:
                        continue
                    positions.append(pos)
                    last_pos = pos

            if len(positions) < 2:
                # 章节识别不到，降级为标准切分
                before = len(result)
                result.extend(self.splitter.split_documents([doc]))
                logger.info(
                    "[SmartSplit] 简历文档 %s 章节识别不足（仅%d处），降级标准切分 → %d chunk",
                    source,
                    len(positions),
                    len(result) - before,
                )
                continue

            # 第一段：章节开始前的头部信息（姓名、联系方式等）
            head_text = text[: positions[0]].strip()
            if head_text:
                result.append(
                    Document(
                        page_content=head_text,
                        metadata={**doc.metadata, "chunk_type": "resume_header"},
                    )
                )

            # 按章节切分，每个章节内容超过 1600 字时继续用标准切分器细分
            section_count = 0
            for i, pos in enumerate(positions):
                end = positions[i + 1] if i + 1 < len(positions) else len(text)
                section_text = text[pos:end].strip()
                if not section_text:
                    continue
                if len(section_text) <= 1600:
                    result.append(
                        Document(
                            page_content=section_text,
                            metadata={**doc.metadata, "chunk_type": "resume_section"},
                        )
                    )
                    section_count += 1
                else:
                    # 超长章节继续切分，chunk_size 较大以保留上下文
                    sub_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1400,
                        chunk_overlap=200,
                        separators=["\n\n", "\n", "。", "；", "!", "?", " ", ""],
                        length_function=len,
                    )
                    sub_docs = sub_splitter.split_documents(
                        [Document(page_content=section_text, metadata={**doc.metadata, "chunk_type": "resume_section"})]
                    )
                    result.extend(sub_docs)
                    section_count += len(sub_docs)

            logger.info(
                "[SmartSplit] 简历文档 %s → 头部1块 + %d 个章节块，共 %d chunk",
                source,
                section_count,
                (1 if head_text else 0) + section_count,
            )

        return result

    def _load_xlsx(self, file_path: str) -> List[Document]:
        """
        使用 pandas 解析 Excel 文件（支持多 sheet），每个 sheet 生成若干 Document

        Args:
            file_path: Excel 文件路径

        Returns:
            文档列表
        """
        file_name = Path(file_path).name
        if Path(file_path).suffix.lower() == ".xls":
            raise ValueError(
                f"暂不支持 .xls 文件: {file_name}。请先另存为 .xlsx 后再上传。"
            )
        docs: List[Document] = []
        try:
            xls = pd.ExcelFile(file_path, engine="openpyxl")
        except Exception as e:
            raise ValueError(f"Excel 文件无法打开: {file_name} — {e}") from e

        for sheet_name in xls.sheet_names:
            try:
                df = xls.parse(sheet_name)
            except Exception as e:
                logger.warning("  跳过 sheet '%s'（解析失败: %s）", sheet_name, e)
                continue

            if df.empty:
                continue

            # 每行转为一段文本，列名作为 key
            rows_text = []
            for idx, row in df.iterrows():
                cells = " | ".join(
                    f"{col}: {val}"
                    for col, val in row.items()
                    if pd.notna(val) and str(val).strip()
                )
                if cells:
                    rows_text.append(f"行{idx + 1}: {cells}")

            if not rows_text:
                continue

            content = f"【Sheet: {sheet_name}】\n" + "\n".join(rows_text)
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": file_name,
                        "file_path": file_path,
                        "sheet_name": sheet_name,
                    },
                )
            )

        if not docs:
            raise ValueError(f"Excel 文件中未读取到任何有效数据: {file_name}")

        return docs

    def _load_docx_with_python_docx(self, file_path: str) -> List[Document]:
        """
        使用 python-docx 解析 Word 文档，完整提取段落、表格、文本框和页眉内容。
        能正确处理简历等复杂排版文档（文本框、页眉信息不再遗漏）。

        Args:
            file_path: docx 文件路径

        Returns:
            文档列表（整篇作为一个 Document）
        """
        import docx  # python-docx
        from docx.oxml.ns import qn

        file_name = Path(file_path).name
        doc = docx.Document(file_path)
        parts: List[str] = []

        # ── 步骤 1：提取页眉内容（简历头部信息常放在页眉里）──
        seen_header_texts: set = set()
        for section in doc.sections:
            try:
                header = section.header
                if header is None:
                    continue
                for para in header.paragraphs:
                    text = para.text.strip()
                    if text and text not in seen_header_texts:
                        seen_header_texts.add(text)
                        parts.append(text)
                # 页眉里的表格
                for tbl in header.tables:
                    rows_text: List[str] = []
                    for row in tbl.rows:
                        cells_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if cells_text:
                            rows_text.append(" | ".join(cells_text))
                    if rows_text:
                        combined = "\n".join(rows_text)
                        if combined not in seen_header_texts:
                            seen_header_texts.add(combined)
                            parts.append(combined)
            except Exception:
                pass  # 某些文档没有页眉，跳过

        # ── 步骤 2：收集所有浮动文本框的内容（txbxContent）──
        txbx_node_ids: set = set()
        txbx_t_ids: set = set()  # 记录文本框里 w:t 的 id，避免步骤3重复提取
        for txbx_content in doc.element.body.findall(".//" + qn("w:txbxContent")):
            txbx_node_ids.add(id(txbx_content))
            texts_in_txbx: List[str] = []
            for para in txbx_content.findall(".//" + qn("w:p")):
                para_text = "".join(
                    (node.text or "")
                    for node in para.iter()
                    if node.tag == qn("w:t")
                ).strip()
                if para_text:
                    texts_in_txbx.append(para_text)
                # 记录文本框内所有 w:t 的 id
                for t_node in para.iter():
                    if t_node.tag == qn("w:t"):
                        txbx_t_ids.add(id(t_node))
            if texts_in_txbx:
                parts.append("\n".join(texts_in_txbx))

        # ── 步骤 3：按顺序遍历 body 提取普通段落和表格（排除文本框内已提取的节点）──
        for block in doc.element.body:
            tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

            if tag == "p":
                # 只提取不在文本框里的 w:t
                para_text = "".join(
                    (node.text or "")
                    for node in block.iter()
                    if node.tag == qn("w:t") and id(node) not in txbx_t_ids
                ).strip()
                if para_text:
                    parts.append(para_text)

            elif tag == "tbl":
                # 表格：每行转为 "col1 | col2 | col3" 格式
                rows_text_list: List[str] = []
                for row in block.findall(".//" + qn("w:tr")):
                    cells: List[str] = []
                    for cell in row.findall(".//" + qn("w:tc")):
                        cell_text = "".join(
                            (node.text or "")
                            for node in cell.iter()
                            if node.tag == qn("w:t") and id(node) not in txbx_t_ids
                        ).strip()
                        cells.append(cell_text)
                    row_text = " | ".join(c for c in cells if c)
                    if row_text:
                        rows_text_list.append(row_text)
                if rows_text_list:
                    parts.append("\n".join(rows_text_list))

        full_text = "\n\n".join(p for p in parts if p.strip()).strip()
        if not full_text:
            raise ValueError(f"python-docx 解析结果为空: {file_name}")

        logger.info(
            "python-docx 解析完成: %s，共 %d 字符", file_name, len(full_text)
        )
        return [
            Document(
                page_content=full_text,
                metadata={"source": file_name, "file_path": file_path},
            )
        ]

    def load_file(self, file_path: str) -> List[Document]:
        """
        根据文件类型自动选择 loader 加载文档

        Args:
            file_path: 文件路径

        Returns:
            加载的文档列表
        """
        file_path = str(Path(file_path).resolve())
        ext = Path(file_path).suffix.lower()
        file_name = Path(file_path).name
        logger.info("加载文件: %s", file_name)

        # XLSX / XLS：使用 pandas 自定义加载
        if ext in (".xlsx", ".xls"):
            docs = self._load_xlsx(file_path)
            return docs

        # PDF：单独捕获异常，提供详细日志
        if ext == ".pdf":
            try:
                loader = PyPDFLoader(file_path)
                docs = loader.load()
            except Exception as e:
                logger.error(
                    "PDF 解析失败: %s — %s（%s）", file_name, type(e).__name__, e
                )
                raise ValueError(f"PDF 解析失败: {file_name} — {e}") from e
            for doc in docs:
                doc.metadata["source"] = file_name
                doc.metadata["file_path"] = file_path
            return docs

        # Markdown：优先 UnstructuredMarkdownLoader，失败降级为 TextLoader
        if ext == ".md":
            try:
                loader = UnstructuredMarkdownLoader(file_path)
                docs = loader.load()
                logger.debug(
                    "Markdown 使用 UnstructuredMarkdownLoader 加载: %s", file_name
                )
            except Exception as e:
                logger.warning(
                    "UnstructuredMarkdownLoader 失败(%s)，降级为 TextLoader: %s",
                    e,
                    file_name,
                )
                loader = TextLoader(file_path, encoding="utf-8")
                docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_name
                doc.metadata["file_path"] = file_path
            return docs

        # DOCX / DOC：优先用 python-docx（能提取文本框/页眉/表格，简历不丢内容）
        # 失败降级 mammoth，再失败降级 Docx2txtLoader
        if ext in (".docx", ".doc"):
            # 1. python-docx 三步骤（页眉+文本框+段落/表格）— 对简历等复杂排版最完整
            try:
                docs = self._load_docx_with_python_docx(file_path)
                return docs
            except Exception as e:
                logger.warning("python-docx 解析失败(%s)，降级为 mammoth: %s", e, file_name)

            # 2. mammoth 兜底（纯文本提取，不含文本框/形状）
            try:
                import mammoth
                with open(file_path, "rb") as fh:
                    result = mammoth.extract_raw_text(fh)
                text = (result.value or "").strip()
                if not text:
                    raise ValueError("mammoth 返回空文本")
                logger.info("mammoth 解析完成: %s，共 %d 字符", file_name, len(text))
                return [
                    Document(
                        page_content=text,
                        metadata={"source": file_name, "file_path": file_path},
                    )
                ]
            except Exception as e:
                logger.warning("mammoth 解析失败(%s)，降级为 Docx2txtLoader: %s", e, file_name)

            # 3. Docx2txtLoader 兜底
            loader = Docx2txtLoader(file_path)
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_name
                doc.metadata["file_path"] = file_path
            return docs

        loaders = {
            ".csv": CSVLoader,
            ".txt": TextLoader,
        }

        loader_cls = loaders.get(ext)
        if not loader_cls:
            raise ValueError(f"不支持的文件类型: {ext}")

        loader = loader_cls(file_path)
        docs = loader.load()

        # 为每个文档添加文件名元数据
        for doc in docs:
            doc.metadata["source"] = file_name
            doc.metadata["file_path"] = file_path

        return docs

    def ingest(
        self,
        file_paths: List[str],
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> int:
        """
        批量导入文档并构建向量索引

        Args:
            file_paths: 文件路径列表

        Returns:
            导入的文档片段数量
        """
        all_docs = []
        failed_files: list[str] = []
        total_files = len(file_paths)

        def report(progress: int) -> None:
            if progress_callback is not None:
                progress_callback(max(0, min(100, progress)))

        if self.vectorstore is None and os.path.exists(self.vector_store_path):
            self.load_store()

        report(5)

        for index, fp in enumerate(file_paths, start=1):
            try:
                file_start = time.perf_counter()
                docs = self.load_file(fp)
                # 使用智能分块替代原有 splitter.split_documents
                chunks = self._smart_split(docs)
                all_docs.extend(chunks)
                file_name = Path(fp).name
                logger.info(
                    "  ✓ %s: %d 个片段 (耗时 %.2fs)",
                    file_name,
                    len(chunks),
                    time.perf_counter() - file_start,
                )
            except Exception as e:
                file_name = Path(fp).name
                logger.error("  ✗ %s: 加载失败 - %s", file_name, e)
                failed_files.append(f"{file_name}: {e}")
                continue

            if total_files:
                report(10 + int(index / total_files * 35))

        if not all_docs:
            detail = "；".join(failed_files[:3]) if failed_files else "未知原因"
            raise ValueError(f"没有成功加载任何文档。失败原因: {detail}")

        logger.info("开始构建向量索引 (共 %d 个片段)", len(all_docs))
        embed_start = time.perf_counter()
        report(55)

        # 分批向量化，每批 32 个 chunk，避免大文件一次性计算导致长时间阻塞
        BATCH_SIZE = 32
        total_chunks = len(all_docs)
        batches = [all_docs[i : i + BATCH_SIZE] for i in range(0, total_chunks, BATCH_SIZE)]
        logger.info("分批向量化: %d 个片段 / %d 批", total_chunks, len(batches))

        for batch_idx, batch in enumerate(batches):
            if self.vectorstore is None:
                self.vectorstore = FAISS.from_documents(batch, self.embeddings)
            else:
                self.vectorstore.add_documents(batch)
            # 更新进度：55% → 90%
            batch_progress = 55 + int((batch_idx + 1) / len(batches) * 35)
            report(batch_progress)
            logger.debug(
                "  批次 %d/%d 完成 (%d 片段)",
                batch_idx + 1,
                len(batches),
                len(batch),
            )

        logger.info("向量化完成，耗时 %.2fs", time.perf_counter() - embed_start)

        # 持久化
        save_start = time.perf_counter()
        self._save_vectorstore_local()
        logger.info(
            "向量索引已保存到: %s (耗时 %.2fs)",
            self.vector_store_path,
            time.perf_counter() - save_start,
        )
        report(100)

        return len(all_docs)

    def load_store(self) -> bool:
        """
        从磁盘加载已有的向量库

        Returns:
            是否加载成功
        """
        if not os.path.exists(self.vector_store_path):
            logger.warning("向量库不存在: %s", self.vector_store_path)
            return False

        try:
            self.vectorstore = self._load_vectorstore_local()
            logger.info("向量库加载成功: %s", self.vector_store_path)
            return True
        except Exception as e:
            logger.error("向量库加载失败: %s", e)
            return False

    def search(self, query: str, k: int = 4) -> List[Document]:
        """
        检索相关文档片段 (纯余弦相似度)

        Args:
            query: 查询文本
            k: 返回的文档数量

        Returns:
            相关文档列表
        """
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        return self.vectorstore.similarity_search(query, k=k)

    def search_with_rerank(
        self, query: str, k: int = 3, fetch_k: int = 10
    ) -> List[Document]:
        """
        二段重排检索: FAISS 粗排 + BGE-Reranker 精排

        流程:
        1. FAISS 检索 Top fetch_k 个候选文档 (余弦相似度粗排)
        2. 使用 BGE-Reranker 对候选文档重新打分 (语义相关性精排)
        3. 返回得分最高的 Top k 个文档

        Args:
            query: 查询文本
            k: 最终返回的文档数量 (默认 3)
            fetch_k: 初次检索的候选文档数量 (默认 10)

        Returns:
            重排后的文档列表 (按相关性降序)
        """
        if self.vectorstore is None:
            raise ValueError("向量库未初始化,请先调用 load_store() 或 ingest()")

        safe_k = max(1, int(k or 1))
        safe_fetch_k = max(safe_k, int(fetch_k or safe_k))
        if safe_fetch_k != fetch_k or safe_k != k:
            logger.warning(
                "Adjusted rerank parameters: k=%s->%d fetch_k=%s->%d",
                k,
                safe_k,
                fetch_k,
                safe_fetch_k,
            )

        # 第一阶段: FAISS 粗排 (检索更多候选)
        candidates = self.vectorstore.similarity_search(query, k=safe_fetch_k)

        if not candidates:
            return []

        try:
            scores = self._predict_rerank_scores(query, candidates)
        except Exception:
            logger.exception("Reranker 失败，回退到 FAISS similarity_search")
            return candidates[:safe_k]

        # 按得分降序排序
        ranked_results = sorted(
            zip(candidates, scores), key=lambda x: x[1], reverse=True
        )

        # 返回 Top k
        top_docs = [doc for doc, score in ranked_results[:safe_k]]

        logger.info(
            "[Rerank] query=%s... fetch_k=%d top_k=%d scores=%s",
            query[:30],
            safe_fetch_k,
            safe_k,
            [f"{s:.4f}" for _, s in ranked_results[:safe_k]],
        )
        for i, (doc, score) in enumerate(ranked_results[:safe_k], 1):
            source = doc.metadata.get("source", "未知")
            logger.debug("  %d. %s (得分: %.4f)", i, source, score)

        return top_docs

    def get_stats(self) -> dict:
        """
        获取向量库统计信息

        Returns:
            统计信息字典
        """
        if self.vectorstore is None:
            return {"status": "未初始化", "total_docs": 0}

        return {
            "status": "已加载",
            "total_docs": self.vectorstore.index.ntotal,
            "store_path": self.vector_store_path,
        }

    def delete_store(self) -> bool:
        """
        删除向量库磁盘文件并重置内存状态

        Returns:
            是否删除成功
        """
        import shutil

        self.vectorstore = None
        if not os.path.exists(self.vector_store_path):
            return False
        try:
            shutil.rmtree(self.vector_store_path)
            logger.info("向量库已删除: %s", self.vector_store_path)
            return True
        except Exception as e:
            logger.error("向量库删除失败: %s", e)
            return False


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
