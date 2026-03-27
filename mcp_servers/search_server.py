"""
联网搜索 MCP Server
基于 Tavily API 提供实时网络搜索功能
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("web-search")


@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """
    搜索互联网获取实时信息

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数 (默认 5)

    Returns:
        格式化的搜索结果,包含标题、链接和摘要
    """
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        return "❌ 未配置 TAVILY_API_KEY,无法使用联网搜索功能"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "query": query,
                    "max_results": max_results,
                    "api_key": api_key,
                    "search_depth": "basic",
                    "include_answer": True,
                },
            )
            response.raise_for_status()
            data = response.json()

            # 提取搜索结果
            results = data.get("results", [])
            answer = data.get("answer", "")

            if not results:
                return f"未找到相关搜索结果: {query}"

            # 格式化输出
            output = []

            if answer:
                output.append(f"【AI 总结】\n{answer}\n")

            output.append(f"【搜索结果 - {query}】\n")

            for i, result in enumerate(results, 1):
                title = result.get("title", "无标题")
                url = result.get("url", "")
                content = result.get("content", "")

                output.append(f"{i}. {title}\n链接: {url}\n摘要: {content}")

            return "\n\n---\n\n".join(output)

    except httpx.HTTPStatusError as e:
        return f"❌ 搜索 API 请求失败 (HTTP {e.response.status_code}): {e.response.text}"
    except httpx.TimeoutException:
        return "❌ 搜索请求超时,请稍后重试"
    except Exception as e:
        return f"❌ 搜索失败: {str(e)}"


@mcp.tool()
async def quick_answer(question: str) -> str:
    """
    快速问答 - 直接返回 AI 总结答案,不返回详细搜索结果

    Args:
        question: 问题

    Returns:
        AI 总结的答案
    """
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        return "❌ 未配置 TAVILY_API_KEY"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "query": question,
                    "max_results": 3,
                    "api_key": api_key,
                    "search_depth": "basic",
                    "include_answer": True,
                },
            )
            response.raise_for_status()
            data = response.json()

            answer = data.get("answer", "")
            if answer:
                return f"【网络搜索答案】\n{answer}"
            else:
                return "未能生成答案,请使用 web_search 查看详细结果"

    except Exception as e:
        return f"❌ 快速问答失败: {str(e)}"


if __name__ == "__main__":
    import sys
    print("启动联网搜索 MCP Server...", file=sys.stderr)
    print("使用 Tavily API 提供实时搜索功能", file=sys.stderr)
    mcp.run(transport="stdio")
