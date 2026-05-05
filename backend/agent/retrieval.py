"""???????????????"""

from __future__ import annotations

import os
import re
import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document

from backend.agent.llm import _stringify_user_input

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.doc_pipeline import DocPipeline

DEFAULT_KB_DOC_CHAR_LIMIT = int(os.getenv("KB_DOC_CHAR_LIMIT", "600"))
DEFAULT_KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
DEFAULT_KB_FETCH_K = int(os.getenv("KB_FETCH_K", "10"))
DEFAULT_KB_RETRIEVAL_MODE = str(os.getenv("KB_RETRIEVAL_MODE", "auto")).strip().lower()

def _normalize_kb_retrieval_mode(mode: Any) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in {"semantic", "keyword", "hybrid", "auto"}:
        return normalized
    return "auto"


def _should_prefer_hybrid_retrieval(query: Any) -> bool:
    text = _stringify_user_input(query).strip()
    if not text:
        return False

    lowered = text.lower()
    exact_match_terms = (
        "字段",
        "列名",
        "参数",
        "接口",
        "编号",
        "版本",
        "路径",
        "文件名",
        "sheet",
        "excel",
        "csv",
        "pdf",
        "json",
        "yaml",
        "markdown",
        "报错",
        "状态码",
        "error code",
    )
    if any(term in lowered for term in exact_match_terms):
        return True

    if any(marker in text for marker in ("`", "/", "\\", "_", ".md", ".pdf", ".docx", ".xlsx", ".csv", ".json", ".yaml", ".yml", ".txt")):
        return True

    if re.search(r"\b[a-z]+[\w.-]*_[\w./:-]+\b", lowered):
        return True
    if re.search(r"\b[a-z]+[\w.-]*\d+[\w.-]*\b", lowered):
        return True
    if re.search(r"[A-Za-z]{2,}[/:.-][A-Za-z0-9_.:-]+", text):
        return True

    ascii_tokens = re.findall(r"\b[A-Za-z0-9_.:/-]+\b", text)
    long_ascii_tokens = [token for token in ascii_tokens if len(token) >= 4]
    if len(long_ascii_tokens) >= 2 and len(text) <= 96:
        return True

    digit_count = sum(char.isdigit() for char in text)
    if digit_count >= 3 and len(text) <= 64:
        return True

    return False


def _choose_kb_retrieval_mode(query: Any, preferred_mode: Any = None) -> str:
    normalized_mode = _normalize_kb_retrieval_mode(preferred_mode or DEFAULT_KB_RETRIEVAL_MODE)
    if normalized_mode != "auto":
        return normalized_mode
    return "hybrid" if _should_prefer_hybrid_retrieval(query) else "semantic"


def _retrieve_kb_documents(
    pipeline: DocPipeline,
    query: Any,
    *,
    top_k: int,
    fetch_k: int,
    preferred_mode: Any = None,
    use_rerank: bool = True,
    log_context: str = "knowledge",
) -> tuple[list[Document], str]:
    mode = _choose_kb_retrieval_mode(query, preferred_mode=preferred_mode)
    safe_top_k = max(1, int(top_k or 1))
    safe_fetch_k = max(safe_top_k, int(fetch_k or safe_top_k))
    query_text = _stringify_user_input(query).strip()

    if mode == "keyword" and hasattr(pipeline, "keyword_search"):
        try:
            docs = pipeline.keyword_search(query_text, k=safe_top_k)
            if docs:
                docs = [
                    Document(
                        page_content=doc.page_content,
                        metadata={
                            **dict(doc.metadata or {}),
                            "retrieval_mode": "keyword",
                            "retrieval_query": query_text,
                            "search_channel": str(
                                (doc.metadata or {}).get("search_channel") or "keyword"
                            ),
                        },
                    )
                    for doc in docs
                ]
                logger.info("[%s] retrieval_mode=keyword query=%s", log_context, query_text[:80])
                return docs, "keyword"
        except Exception:
            logger.exception("[%s] keyword retrieval failed query=%s", log_context, query_text)

    if mode == "hybrid" and hasattr(pipeline, "hybrid_search"):
        try:
            docs = pipeline.hybrid_search(
                query_text,
                k=safe_top_k,
                fetch_k=safe_fetch_k,
                use_rerank=use_rerank,
            )
            if docs:
                actual_mode = "hybrid_rerank" if use_rerank else "hybrid"
                docs = [
                    Document(
                        page_content=doc.page_content,
                        metadata={
                            **dict(doc.metadata or {}),
                            "retrieval_mode": actual_mode,
                            "retrieval_query": query_text,
                            "search_channel": str(
                                (doc.metadata or {}).get("search_channel") or actual_mode
                            ),
                        },
                    )
                    for doc in docs
                ]
                logger.info("[%s] retrieval_mode=%s query=%s", log_context, actual_mode, query_text[:80])
                return docs, actual_mode
        except Exception:
            logger.exception("[%s] hybrid retrieval failed query=%s", log_context, query_text)

    if use_rerank:
        docs = [
            Document(
                page_content=doc.page_content,
                metadata={
                    **dict(doc.metadata or {}),
                    "retrieval_mode": "semantic_rerank",
                    "retrieval_query": query_text,
                    "search_channel": str(
                        (doc.metadata or {}).get("search_channel") or "semantic_rerank"
                    ),
                },
            )
            for doc in pipeline.search_with_rerank(query_text, k=safe_top_k, fetch_k=safe_fetch_k)
        ]
        logger.info("[%s] retrieval_mode=semantic_rerank query=%s", log_context, query_text[:80])
        return docs, "semantic_rerank"

    docs = [
        Document(
            page_content=doc.page_content,
            metadata={
                **dict(doc.metadata or {}),
                "retrieval_mode": "semantic",
                "retrieval_query": query_text,
                "search_channel": str(
                    (doc.metadata or {}).get("search_channel") or "semantic"
                ),
            },
        )
        for doc in pipeline.search(query_text, k=safe_top_k)
    ]
    logger.info("[%s] retrieval_mode=semantic query=%s", log_context, query_text[:80])
    return docs, "semantic"


def _trim_knowledge_doc_content(content: str, max_chars: int = DEFAULT_KB_DOC_CHAR_LIMIT) -> str:
    cleaned = re.sub(r"\s+", " ", (content or "")).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + " ...[节选]"


def _dedupe_documents(documents: list[Document], limit: int = 8) -> list[Document]:
    unique: list[Document] = []
    seen: set[str] = set()
    for doc in documents:
        source = str(doc.metadata.get("source", ""))
        signature = f"{source}|{doc.page_content[:180].strip()}"
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(doc)
        if len(unique) >= limit:
            break
    return unique


def _merge_same_source_chunks(documents: list[Document], max_chars_per_source: int = 3000) -> list[Document]:
    """
    将来自同一源文件的多个 chunk 合并为一个完整上下文块。
    对简历类文档特别有效：避免检索时只拿到半截工作经历。
    每个源文件合并后的内容上限为 max_chars_per_source 字符。
    """
    from collections import OrderedDict
    # 按 source 聚合，保持首次出现顺序
    source_groups: OrderedDict[str, list[str]] = OrderedDict()
    source_meta: dict[str, dict] = {}

    for doc in documents:
        source = str(doc.metadata.get("source", "未知来源"))
        if source not in source_groups:
            source_groups[source] = []
            source_meta[source] = doc.metadata
        content = doc.page_content.strip()
        if content:
            source_groups[source].append(content)

    merged: list[Document] = []
    for source, parts in source_groups.items():
        # 去重相邻重复片段
        deduped: list[str] = []
        for part in parts:
            if not deduped or part[:60] != deduped[-1][:60]:
                deduped.append(part)

        combined = "\n\n".join(deduped)
        if len(combined) > max_chars_per_source:
            combined = combined[:max_chars_per_source].rstrip() + "\n...[内容已截断，仅展示前段]"

        merged.append(
            Document(
                page_content=combined,
                metadata={**source_meta[source], "merged_chunks": len(deduped)},
            )
        )

    return merged
