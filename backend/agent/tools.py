"""Built-in tool definitions and enablement for the agent runtime."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from langchain_core.tools import tool

from backend.agent.retrieval import (
    DEFAULT_KB_DOC_CHAR_LIMIT,
    DEFAULT_KB_FETCH_K,
    DEFAULT_KB_TOP_K,
    _dedupe_documents,
    _merge_same_source_chunks,
    _retrieve_kb_documents,
    _trim_knowledge_doc_content,
)
from backend.agent.tool_registry import _build_enabled_tool_directory, list_enabled_builtin_tool_specs
from search_runtime.service import fetch_webpage_text, quick_answer_text, search_web_text

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.doc_pipeline import DocPipeline


def create_tools(
    pipeline: DocPipeline,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
):
    """
    创建所有工具函数
    
    Args:
        pipeline: DocPipeline 实例
    
    Returns:
        工具函数列表
    """
    @tool
    async def query_knowledge(question: str, top_k: int = DEFAULT_KB_TOP_K) -> str:
        """
        从企业内部知识库中检索相关文档片段（自动选择语义/混合检索）

        Args:
            question: 用户问题
            top_k: 返回的文档片段数量，默认取 `DEFAULT_KB_TOP_K`

        Returns:
            格式化的文档片段,包含来源信息
        """
        try:
            if not knowledge_base_enabled:
                return "知识库引用已关闭，如需使用请打开知识库开关。"
            if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
                pipeline.load_store()
            
            if pipeline.vectorstore is None:
                return "⚠️ 知识库未初始化,请先上传文档"

            docs, retrieval_mode = _retrieve_kb_documents(
                pipeline,
                question,
                top_k=top_k,
                fetch_k=DEFAULT_KB_FETCH_K,
                preferred_mode="auto",
                use_rerank=True,
                log_context="query_knowledge",
            )
            docs = _dedupe_documents(docs, limit=top_k)

            if not docs:
                return "未找到相关文档"

            # 当检索结果来自同一源文件（如简历），合并 chunk 避免信息割裂
            unique_sources = {doc.metadata.get("source", "") for doc in docs}
            if len(unique_sources) < len(docs):
                # 存在来自同一文件的多个 chunk，执行合并
                docs = _merge_same_source_chunks(docs, max_chars_per_source=3600)
                logger.info(
                    "[query_knowledge] 合并同源 chunk → %d 个来源块", len(docs)
                )

            results = []
            sources_meta = []
            for i, doc in enumerate(docs, 1):
                source = doc.metadata.get("source", "未知来源")
                # 合并后内容较长，适当提高单片段字符上限
                max_chars = 2400 if doc.metadata.get("merged_chunks", 1) > 1 else DEFAULT_KB_DOC_CHAR_LIMIT
                content = _trim_knowledge_doc_content(doc.page_content, max_chars=max_chars)
                results.append(f"【文档 {i}: {source}】\n{content}")
                sources_meta.append({
                    "type": "doc",
                    "title": source,
                    "snippet": content[:200],
                    "index": i,
                    "retrieval_mode": str(doc.metadata.get("retrieval_mode") or retrieval_mode),
                    "search_channel": str(doc.metadata.get("search_channel") or "").strip(),
                    "score": doc.metadata.get("search_score"),
                    "matched_terms": doc.metadata.get("matched_terms") or [],
                    "retrieval_query": str(doc.metadata.get("retrieval_query") or question).strip(),
                    "feedback_boost": float(doc.metadata.get("feedback_boost", 0.0) or 0.0),
                    "feedback_net": int(doc.metadata.get("feedback_net", 0) or 0),
                    "feedback_positive_count": int(doc.metadata.get("feedback_positive_count", 0) or 0),
                    "feedback_negative_count": int(doc.metadata.get("feedback_negative_count", 0) or 0),
                    "version_label": str(doc.metadata.get("kb_version_label") or "").strip(),
                    "lifecycle_status": str(doc.metadata.get("kb_lifecycle_status") or "").strip(),
                    "is_latest": bool(doc.metadata.get("kb_is_latest", False)),
                    "is_expired": bool(doc.metadata.get("kb_is_expired", False)),
                })

            # Embed sources metadata as a JSON comment at the end for execute_tool to parse
            import json as _json
            sources_marker = f"\n\n__SOURCES__:{_json.dumps(sources_meta, ensure_ascii=False)}"
            return "\n\n---\n\n".join(results) + sources_marker

        except Exception as e:
            logger.exception("tool=query_knowledge 检索失败")
            return f"❌ 检索失败: {str(e)}"

    @tool
    async def reload_knowledge_base() -> str:
        """
        重新加载知识库 (在文档更新后调用)

        Returns:
            加载状态信息
        """
        try:
            if not knowledge_base_enabled:
                return "知识库引用已关闭，如需使用请打开知识库开关。"
            success = pipeline.load_store()
            if success:
                stats = pipeline.get_stats()
                return f"✓ 知识库重载成功\n总文档数: {stats['total_docs']}\n路径: {stats['store_path']}"
            else:
                return "⚠️ 知识库不存在或加载失败"
        except Exception as e:
            logger.exception("tool=reload_knowledge_base 重载失败")
            return f"❌ 重载失败: {str(e)}"

    @tool
    async def get_knowledge_stats() -> str:
        """
        获取知识库统计信息

        Returns:
            知识库状态和统计数据
        """
        try:
            if not knowledge_base_enabled:
                return "知识库引用已关闭，如需使用请打开知识库开关。"
            if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
                pipeline.load_store()
            
            stats = pipeline.get_stats()
            return f"""知识库状态: {stats['status']}
总文档片段数: {stats.get('total_docs', 0)}
存储路径: {stats.get('store_path', 'N/A')}"""
        except Exception as e:
            logger.exception("tool=get_knowledge_stats 获取统计失败")
            return f"❌ 获取统计信息失败: {str(e)}"

    @tool
    async def web_search(search_query: str, max_results: int = 5) -> str:
        """
        搜索互联网获取实时信息

        Args:
            search_query: 搜索关键词
            max_results: 最大返回结果数 (默认 5)

        Returns:
            格式化的搜索结果,包含标题、链接和摘要
        """
        if not web_search_enabled:
            return "联网搜索已关闭，如需使用请点击输入框上方的「🌐 联网搜索」开关。"

        return await search_web_text(search_query, max_results=max_results)

    @tool
    async def quick_answer(user_question: str) -> str:
        """
        快速问答 - 直接返回 AI 总结答案,不返回详细搜索结果

        Args:
            user_question: 问题

        Returns:
            AI 总结的答案
        """
        if not web_search_enabled:
            return "联网搜索已关闭，如需使用请点击输入框上方的「🌐 联网搜索」开关。"

        return await quick_answer_text(user_question)

    @tool
    async def fetch_webpage(url: str) -> str:
        """
        抓取指定网页的全文内容

        Args:
            url: 网页 URL

        Returns:
            网页的纯文本内容（截断至 8000 字符）
        """
        if not web_search_enabled:
            return "联网搜索已关闭，如需使用请点击输入框上方的「🌐 联网搜索」开关。"
        return await fetch_webpage_text(url)

    declared_tools = {
        "query_knowledge": query_knowledge,
        "reload_knowledge_base": reload_knowledge_base,
        "get_knowledge_stats": get_knowledge_stats,
        "web_search": web_search,
        "quick_answer": quick_answer,
        "fetch_webpage": fetch_webpage,
    }
    return [
        declared_tools[spec.name]
        for spec in list_enabled_builtin_tool_specs(
            knowledge_base_enabled=knowledge_base_enabled,
            web_search_enabled=web_search_enabled,
        )
        if spec.name in declared_tools
    ]
