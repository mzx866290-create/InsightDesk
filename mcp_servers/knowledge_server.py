"""
企业知识库 MCP Server
提供内部文档检索和向量库管理功能
"""

import json
import sys
import os
from pathlib import Path

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from backend.doc_pipeline import DocPipeline

mcp = FastMCP("knowledge-base")
DEFAULT_KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
DEFAULT_KB_FETCH_K = int(os.getenv("KB_FETCH_K", "10"))

# 初始化文档管道 (延迟加载模型和向量库)
pipeline = DocPipeline()


def _ensure_store_loaded():
    """首次调用时加载向量库"""
    if pipeline.vectorstore is None and os.path.exists(pipeline.vector_store_path):
        pipeline.load_store()


def _append_sources_marker(text: str, sources: list[dict]) -> str:
    return f"{text}\n\n__SOURCES__:{json.dumps(sources, ensure_ascii=False)}"


@mcp.tool()
async def query_knowledge(question: str, top_k: int = DEFAULT_KB_TOP_K) -> str:
    """
    从企业内部知识库中检索相关文档片段

    Args:
        question: 用户问题
        top_k: 返回的文档片段数量 (默认 4)

    Returns:
        格式化的文档片段,包含来源信息
    """
    try:
        _ensure_store_loaded()
        if pipeline.vectorstore is None:
            return "⚠️ 知识库未初始化,请先上传文档"

        docs = pipeline.search_with_rerank(
            question,
            k=top_k,
            fetch_k=DEFAULT_KB_FETCH_K,
        )

        if not docs:
            return "未找到相关文档"

        # 格式化返回结果
        results = []
        sources = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "未知来源")
            content = doc.page_content.strip()
            results.append(f"【文档 {i}: {source}】\n{content}")
            sources.append(
                {
                    "type": "doc",
                    "title": source,
                    "snippet": content[:200],
                    "index": i,
                }
            )

        return _append_sources_marker("\n\n---\n\n".join(results), sources)

    except Exception as e:
        return f"❌ 检索失败: {str(e)}"


@mcp.tool()
async def reload_knowledge_base() -> str:
    """
    重新加载知识库 (在文档更新后调用)

    Returns:
        加载状态信息
    """
    try:
        success = pipeline.load_store()
        if success:
            stats = pipeline.get_stats()
            return f"✓ 知识库重载成功\n总文档数: {stats['total_docs']}\n路径: {stats['store_path']}"
        else:
            return "⚠️ 知识库不存在或加载失败"
    except Exception as e:
        return f"❌ 重载失败: {str(e)}"


@mcp.tool()
async def get_knowledge_stats() -> str:
    """
    获取知识库统计信息

    Returns:
        知识库状态和统计数据
    """
    try:
        _ensure_store_loaded()
        stats = pipeline.get_stats()
        return f"""知识库状态: {stats['status']}
总文档片段数: {stats.get('total_docs', 0)}
存储路径: {stats.get('store_path', 'N/A')}"""
    except Exception as e:
        return f"❌ 获取统计信息失败: {str(e)}"


if __name__ == "__main__":
    import sys
    print("启动企业知识库 MCP Server...", file=sys.stderr)
    print(f"向量库状态: {pipeline.get_stats()}", file=sys.stderr)
    mcp.run(transport="stdio")
