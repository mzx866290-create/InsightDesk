"""Document loading and smart splitting.

Split out of backend.doc_pipeline as a mixin; composed by DocPipeline.
"""

"""
文档处理与向量化管道
支持 PDF、Word、Markdown、CSV 等格式的文档加载、分块、向量化和检索
"""

import logging
from pathlib import Path
from typing import Any, List
import pandas as pd
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    CSVLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document



logger = logging.getLogger(__name__)

from backend.doc_pipeline_constants import (  # noqa: F401
    KEYWORD_TOKEN_PATTERN,
    VERSION_TOKEN_PATTERN,
    DATE_TOKEN_PATTERN,
    COMPACT_DATE_TOKEN_PATTERN,
    EXPIRY_HINT_PATTERN,
)


class DocPipelineLoadersMixin:
    _resume_detect_keywords: Any
    _resume_section_keywords: Any
    splitter: Any

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
        loader: Any
        logger.info("加载文件: %s", file_name)

        # XLSX / XLS：使用 pandas 自定义加载
        if ext in (".xlsx", ".xls"):
            docs = self._load_xlsx(file_path)
            return docs

        # PDF：单独捕获异常，提供详细日志
        if ext == ".pdf":
            try:
                loader = PyPDFLoader(file_path)
                docs = list(loader.load())
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
                docs = list(loader.load())
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
                docs = list(loader.load())
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
            docs = list(loader.load())
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
        docs = list(loader.load())

        # 为每个文档添加文件名元数据
        for doc in docs:
            doc.metadata["source"] = file_name
            doc.metadata["file_path"] = file_path

        return docs

