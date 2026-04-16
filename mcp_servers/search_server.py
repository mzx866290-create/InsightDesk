"""
联网搜索 MCP Server
基于统一的 search_runtime 服务提供联网搜索、快速问答和网页抓取能力。
"""

from pathlib import Path
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from search_runtime.service import fetch_webpage_text, quick_answer_text, search_web_text

load_dotenv()

mcp = FastMCP("web-search")


@mcp.tool()
async def web_search(search_query: str, max_results: int = 5) -> str:
    """
    搜索互联网获取实时信息。

    Args:
        search_query: 搜索关键词
        max_results: 最大返回结果数
    """
    return await search_web_text(search_query, max_results=max_results)


@mcp.tool()
async def quick_answer(user_question: str) -> str:
    """
    基于联网搜索返回简短答案。

    Args:
        user_question: 用户问题
    """
    return await quick_answer_text(user_question)


@mcp.tool()
async def fetch_webpage(url: str) -> str:
    """
    抓取指定网页的正文内容。

    Args:
        url: 网页地址
    """
    return await fetch_webpage_text(url)


if __name__ == "__main__":
    print("启动联网搜索 MCP Server...", file=sys.stderr)
    print("使用统一 search_runtime 提供联网搜索能力", file=sys.stderr)
    mcp.run(transport="stdio")
