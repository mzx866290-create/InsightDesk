"""Vector-store persistence: FAISS staging, save/load, ingest.

Split out of backend.doc_pipeline as a mixin; composed by DocPipeline.
"""

"""
文档处理与向量化管道
支持 PDF、Word、Markdown、CSV 等格式的文档加载、分块、向量化和检索
"""

import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, List, Optional
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from backend.core.storage_runtime import (
    VECTOR_STORE_PROVIDER_FAISS,
)



logger = logging.getLogger(__name__)

from backend.doc_pipeline_constants import (  # noqa: F401
    KEYWORD_TOKEN_PATTERN,
    VERSION_TOKEN_PATTERN,
    DATE_TOKEN_PATTERN,
    COMPACT_DATE_TOKEN_PATTERN,
    EXPIRY_HINT_PATTERN,
)


class DocPipelineStoreMixin:
    _all_index_documents: Any
    _prepare_documents_for_index: Any
    _smart_split: Any
    embeddings: Any
    load_file: Any
    vector_store_adapter: Any
    vector_store_path: Any
    vectorstore: Any

    @staticmethod
    def _path_has_non_ascii(path: str) -> bool:
        try:
            path.encode("ascii")
            return False
        except UnicodeEncodeError:
            return True

    def _should_use_faiss_staging_dir(self) -> bool:
        if self.vector_store_adapter.provider != VECTOR_STORE_PROVIDER_FAISS:
            return False
        resolved = str(Path(self.vector_store_path).resolve())
        return sys.platform == "win32" and self._path_has_non_ascii(resolved)

    def _make_faiss_staging_dir(self, prefix: str) -> Path:
        base_dir = Path(tempfile.gettempdir()) / "ai_kb_faiss"
        base_dir.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=f"{prefix}_", dir=str(base_dir)))

    def _save_vectorstore_local(self) -> None:
        vectorstore = self.vectorstore
        if vectorstore is None:
            raise ValueError("Vector store is not initialized.")
        if self.vector_store_adapter.provider != VECTOR_STORE_PROVIDER_FAISS:
            self.vector_store_adapter.save(vectorstore, path=self.vector_store_path)
            return

        target_dir = Path(self.vector_store_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        if not self._should_use_faiss_staging_dir():
            vectorstore.save_local(str(target_dir))
            return

        staging_dir = self._make_faiss_staging_dir("save")
        logger.info(
            "FAISS save workaround enabled for Windows non-ASCII path: %s",
            target_dir,
        )
        try:
            vectorstore.save_local(str(staging_dir))
            for file_name in ("index.faiss", "index.pkl"):
                shutil.copy2(staging_dir / file_name, target_dir / file_name)
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def _load_vectorstore_local(self) -> Any:
        if self.vector_store_adapter.provider != VECTOR_STORE_PROVIDER_FAISS:
            return self.vector_store_adapter.load(
                embeddings=self.embeddings,
                path=self.vector_store_path,
            )

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

        existing_docs: list[Document] = []
        if (
            self.vectorstore is None
            and self.vector_store_adapter.provider == VECTOR_STORE_PROVIDER_FAISS
            and os.path.exists(self.vector_store_path)
        ):
            self.load_store()
        if self.vectorstore is not None:
            try:
                existing_docs = self._all_index_documents()
            except Exception:
                logger.exception("Failed to read existing documents before ingest")
                existing_docs = []

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
        prepared_docs = self._prepare_documents_for_index([*existing_docs, *all_docs])
        logger.info(
            "Preparing index rebuild: existing=%d new=%d final=%d",
            len(existing_docs),
            len(all_docs),
            len(prepared_docs),
        )
        embed_start = time.perf_counter()
        report(55)

        # 分批向量化，每批 32 个 chunk，避免大文件一次性计算导致长时间阻塞
        BATCH_SIZE = 32
        total_chunks = len(prepared_docs)
        batches = [prepared_docs[i : i + BATCH_SIZE] for i in range(0, total_chunks, BATCH_SIZE)]
        self.vectorstore = None
        logger.info("分批向量化: %d 个片段 / %d 批", total_chunks, len(batches))

        for batch_idx, batch in enumerate(batches):
            if self.vectorstore is None:
                self.vectorstore = self.vector_store_adapter.from_documents(batch, self.embeddings)
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

        return len(prepared_docs)

    def load_store(self) -> bool:
        """
        从磁盘加载已有的向量库

        Returns:
            是否加载成功
        """
        if (
            self.vector_store_adapter.provider == VECTOR_STORE_PROVIDER_FAISS
            and not os.path.exists(self.vector_store_path)
        ):
            logger.warning("向量库不存在: %s", self.vector_store_path)
            return False

        try:
            self.vectorstore = self._load_vectorstore_local()
            logger.info("向量库加载成功: %s", self.vector_store_path)
            return True
        except Exception as e:
            logger.error("向量库加载失败: %s", e)
            return False

