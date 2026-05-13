"""Small helpers shared by the LangGraph agent workflow."""

import logging
import time
from typing import Any, Literal, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from search_runtime.service import rewrite_search_query_for_web, rewrite_search_query_with_llm

logger = logging.getLogger(__name__)


async def _rewrite_search_query(llm, user_input: str, chat_history: list[BaseMessage]) -> str:
    """
    重写搜索查询以包含对话上下文

    Args:
        llm: LLM 实例
        user_input: 用户原始输入
        chat_history: 对话历史

    Returns:
        优化后的搜索查询
    """
    fallback_query = rewrite_search_query_for_web(user_input)

    history_text = ""
    recent_history = chat_history[-4:]
    for msg in recent_history:
        if isinstance(msg, HumanMessage):
            history_text += f"用户: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            history_text += f"助手: {msg.content}\n"

    try:
        normalized = await rewrite_search_query_with_llm(
            llm,
            user_input,
            chat_history=history_text,
            timeout_seconds=20,
        )
        logger.info("[QueryRewrite] original=%s -> rewritten=%s", user_input[:50], normalized[:80])
        return normalized if normalized else fallback_query
    except Exception:
        logger.exception("[QueryRewrite] 查询重写失败")
        return fallback_query


class AgentState(TypedDict):
    """LangGraph Agent 状态"""

    input: Any
    chat_history: list[BaseMessage]
    tool_choice: str
    tool_result: str
    sources: list
    retrieval_meta: dict[str, Any]
    output: str


def _graph_configurable_value(config: Any, key: str, default: Any) -> Any:
    if not config:
        return default
    try:
        configurable = config.get("configurable", {})
    except Exception:
        configurable = {}
    if not isinstance(configurable, dict):
        return default
    return configurable.get(key, default)


def _emit_workflow_state(
    config: Any,
    node_name: str,
    status: Literal["running", "completed", "failed"],
    *,
    duration_ms: Optional[int] = None,
    tool_name: str = "",
    tool_params: Optional[dict[str, Any]] = None,
    tool_result_summary: str = "",
    retrieval_meta: Optional[dict[str, Any]] = None,
    error: str = "",
) -> None:
    sink = _graph_configurable_value(config, "workflow_event_sink", None)
    if not callable(sink):
        return

    payload: dict[str, Any] = {
        "type": "workflow_state",
        "node_name": node_name,
        "status": status,
        "timestamp": int(time.time() * 1000),
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if tool_name:
        payload["tool_name"] = tool_name
    if tool_params:
        payload["tool_params"] = tool_params
    if tool_result_summary:
        payload["tool_result_summary"] = tool_result_summary
    if retrieval_meta:
        payload["retrieval_meta"] = retrieval_meta
    if error:
        payload["error"] = error

    try:
        sink(payload)
    except Exception:
        logger.exception("[LangGraph] workflow event sink failed node=%s", node_name)


def _emit_stream_item(config: Any, item: Any) -> None:
    sink = _graph_configurable_value(config, "stream_item_sink", None)
    if not callable(sink):
        return
    try:
        sink(item)
    except Exception:
        logger.exception("[LangGraph] stream item sink failed")
