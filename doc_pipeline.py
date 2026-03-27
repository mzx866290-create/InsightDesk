"""
文档处理与向量化管道
支持 PDF、Word、Markdown、CSV 等格式的文档加载、分块、向量化和检索
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional
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
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class DocPipeline:
    """文档处理管道类"""

    def __init__(
        self,
        embedding_model: Optional[str] = None,
        device: str = "cpu",
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
            "EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"
        )
        self.device = device or os.getenv("EMBEDDING_DEVICE", "cpu")
        self.vector_store_path = vector_store_path or os.getenv(
            "VECTOR_STORE_PATH", "./vector_store"
        )

        # 延迟加载: 首次使用时才加载模型,避免启动卡顿
        self._embeddings = None
        self._reranker = None  # 延迟加载 Reranker 模型

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=80,
            separators=["\n\n", "\n", "。", "；", "!", "?", " ", ""],
            length_function=len,
        )

        self.vectorstore: Optional[FAISS] = None

    @property
    def embeddings(self):
        """延迟加载 Embedding 模型"""
        if self._embeddings is None:
            logger.info("加载 Embedding 模型: %s (设备: %s)", self.embedding_model, self.device)
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model,
                model_kwargs={"device": self.device},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("Embedding 模型加载完成")
        return self._embeddings

    @property
    def reranker(self):
        """延迟加载 Reranker 模型 (用于二段重排)"""
        if self._reranker is None:
            reranker_model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
            logger.info("加载 Reranker 模型: %s", reranker_model)
            self._reranker = CrossEncoder(reranker_model, max_length=512)
            logger.info("Reranker 模型加载完成")
        return self._reranker

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

        loaders = {
            ".pdf": PyPDFLoader,
            ".docx": Docx2txtLoader,
            ".doc": Docx2txtLoader,
            ".md": UnstructuredMarkdownLoader,
            ".csv": CSVLoader,
            ".txt": TextLoader,
        }

        loader_cls = loaders.get(ext)
        if not loader_cls:
            raise ValueError(f"不支持的文件类型: {ext}")

        file_name = Path(file_path).name
        logger.info("加载文件: %s", file_name)
        loader = loader_cls(file_path)
        docs = loader.load()

        # 为每个文档添加文件名元数据
        for doc in docs:
            doc.metadata["source"] = Path(file_path).name
            doc.metadata["file_path"] = file_path

        return docs

    def ingest(self, file_paths: List[str]) -> int:
        """
        批量导入文档并构建向量索引

        Args:
            file_paths: 文件路径列表

        Returns:
            导入的文档片段数量
        """
        all_docs = []

        for fp in file_paths:
            try:
                docs = self.load_file(fp)
                chunks = self.splitter.split_documents(docs)
                all_docs.extend(chunks)
                file_name = Path(fp).name
                logger.info("  ✓ %s: %d 个片段", file_name, len(chunks))
            except Exception as e:
                file_name = Path(fp).name
                logger.error("  ✗ %s: 加载失败 - %s", file_name, e)
                continue

        if not all_docs:
            raise ValueError("没有成功加载任何文档")

        logger.info("开始构建向量索引 (共 %d 个片段)", len(all_docs))

        if self.vectorstore is None:
            self.vectorstore = FAISS.from_documents(all_docs, self.embeddings)
        else:
            # 增量添加到现有索引
            new_vectorstore = FAISS.from_documents(all_docs, self.embeddings)
            self.vectorstore.merge_from(new_vectorstore)

        # 持久化
        os.makedirs(self.vector_store_path, exist_ok=True)
        self.vectorstore.save_local(self.vector_store_path)
        logger.info("向量索引已保存到: %s", self.vector_store_path)

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
            self.vectorstore = FAISS.load_local(
                self.vector_store_path,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
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

    def search_with_rerank(self, query: str, k: int = 3, fetch_k: int = 10) -> List[Document]:
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
        
        # 第一阶段: FAISS 粗排 (检索更多候选)
        candidates = self.vectorstore.similarity_search(query, k=fetch_k)
        
        if not candidates:
            return []
        
        # 第二阶段: Reranker 精排
        # 构造 (query, doc) 对
        pairs = [[query, doc.page_content] for doc in candidates]
        
        # 使用 CrossEncoder 计算相关性得分
        scores = self.reranker.predict(pairs)
        
        # 按得分降序排序
        ranked_results = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 返回 Top k
        top_docs = [doc for doc, score in ranked_results[:k]]
        
        logger.info(
            "[Rerank] query=%s... fetch_k=%d top_k=%d scores=%s",
            query[:30],
            fetch_k,
            k,
            [f"{s:.4f}" for _, s in ranked_results[:k]],
        )
        for i, (doc, score) in enumerate(ranked_results[:k], 1):
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    pipeline = DocPipeline()

    test_files = ["test.pdf", "test.docx", "test.md"]
    existing_files = [f for f in test_files if os.path.exists(f)]

    if existing_files:
        count = pipeline.ingest(existing_files)
        logger.info("导入完成: %d 个文档片段", count)

        results = pipeline.search("测试查询", k=3)
        logger.info("检索结果 (%d 条):", len(results))
        for i, doc in enumerate(results, 1):
            logger.info("%d. %s: %s...", i, doc.metadata.get("source", "未知"), doc.page_content[:100])
    else:
        logger.warning("未找到测试文件,请先创建 test.pdf/test.docx/test.md")
