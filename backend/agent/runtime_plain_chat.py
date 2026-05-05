"""Direct multimodal and plain-text chat runtime helpers."""

from typing import Any, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from backend.agent.dashboard_payload import _should_generate_dashboard
from backend.agent.history import _preserve_system_messages_with_recent_history
from backend.agent.llm import (
    _ThinkTagStreamFilter,
    _ainvoke_llm_with_timeout,
    _astream_llm_with_timeout,
    _has_image_input,
    _stringify_user_input,
    _strip_think_tags,
)
from backend.agent.runtime_intent import _normalized_intent_text


def _looks_like_resume_request(user_input: Any) -> bool:
    text = _stringify_user_input(user_input)
    return any(keyword in text for keyword in ("简历", "履历", "CV", "求职"))


def _heuristic_langgraph_tool_choice(
    user_input: Any,
    *,
    knowledge_base_enabled: bool,
    web_search_enabled: bool,
) -> str:
    text = _normalized_intent_text(user_input)
    if not text:
        return ""

    if knowledge_base_enabled:
        if "知识库" in text and any(
            keyword in text for keyword in ("重载", "重新加载", "刷新", "重新索引")
        ):
            return "5"

        if "知识库" in text and any(
            keyword in text
            for keyword in ("状态", "统计", "多少", "几份", "几个", "路径", "健康", "监控")
        ):
            return "4"

        if "知识库" in text:
            return "1"

        file_scope_markers = ("上传", "附件", "文档", "材料", "资料", "简历", "履历", "库里")
        kb_actions = ("读取", "读到", "检索", "搜索", "总结", "复述", "概括", "提取", "分析", "重写", "润色", "改写")
        if any(marker in text for marker in file_scope_markers) and any(
            action in text for action in kb_actions
        ):
            return "1"

        if _looks_like_resume_request(user_input) and any(
            marker in text for marker in ("我的", "之前", "上传", "已有", "资料", "经历", "项目")
        ):
            return "1"

    if web_search_enabled and any(keyword in text for keyword in ("最新", "今天", "新闻", "联网", "网上")):
        return "2"

    return ""


async def _direct_multimodal_answer(
    llm,
    user_input: Any,
    chat_history: list[BaseMessage],
    system_prompt: Optional[str] = None,
) -> str:
    messages: list[BaseMessage] = [
        SystemMessage(
            content=system_prompt
            or "你是一个企业知识库助手。当前用户上传了图片，请直接基于图片和问题作答。不要调用任何工具，始终用中文回答。"
        )
    ]
    messages.extend(_preserve_system_messages_with_recent_history(chat_history, max_recent=8))
    messages.append(HumanMessage(content=user_input))
    response = await _ainvoke_llm_with_timeout(llm, messages)
    content = response.content
    if isinstance(content, str):
        return _strip_think_tags(content)
    return _strip_think_tags(_stringify_user_input(content))


def _build_plain_text_chat_messages(
    user_input: Any,
    chat_history: list[BaseMessage],
    *,
    system_prompt: Optional[str] = None,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [
        SystemMessage(
            content=system_prompt
            or "你是一个中文写作与问答助手。当前请求不需要调用任何工具，请直接基于上下文回答用户问题。始终用中文回答。"
        )
    ]
    messages.extend(_preserve_system_messages_with_recent_history(chat_history, max_recent=8))
    messages.append(HumanMessage(content=user_input))
    return messages


def _should_bypass_tools_for_plain_text_chat(
    user_input: Any,
    *,
    knowledge_base_enabled: bool,
    web_search_enabled: bool,
) -> bool:
    """纯文本创作/问答场景直接走聊天链路，避免云端模型被 Agent/工具额外拖慢。"""
    if _has_image_input(user_input):
        return False
    if _should_generate_dashboard(user_input):
        return False

    text = _stringify_user_input(user_input).strip()
    if not text:
        return False

    heuristic_choice = _heuristic_langgraph_tool_choice(
        user_input,
        knowledge_base_enabled=knowledge_base_enabled,
        web_search_enabled=web_search_enabled,
    )
    return not heuristic_choice


def _plain_text_chat_timeout_seconds(
    user_input: Any,
    chat_history: list[BaseMessage],
) -> float:
    """长文本纯聊天适当放宽超时，降低小说/续写类请求被过早截断的概率。"""
    total_chars = len(_stringify_user_input(user_input))
    recent_history = _preserve_system_messages_with_recent_history(chat_history, max_recent=6)
    for message in recent_history:
        content = getattr(message, "content", "")
        total_chars += len(_stringify_user_input(content))

    if total_chars >= 9000:
        return 180.0
    if total_chars >= 5000:
        return 140.0
    if total_chars >= 2500:
        return 110.0
    return 90.0


async def _direct_plain_text_answer(
    llm,
    user_input: Any,
    chat_history: list[BaseMessage],
    *,
    system_prompt: Optional[str] = None,
) -> str:
    messages = _build_plain_text_chat_messages(
        user_input,
        chat_history,
        system_prompt=system_prompt,
    )
    response = await _ainvoke_llm_with_timeout(
        llm,
        messages,
        timeout_seconds=_plain_text_chat_timeout_seconds(user_input, chat_history),
    )
    content = response.content
    if isinstance(content, str):
        return _strip_think_tags(content)
    return _strip_think_tags(_stringify_user_input(content))


async def _astream_plain_text_answer(
    llm,
    user_input: Any,
    chat_history: list[BaseMessage],
    *,
    system_prompt: Optional[str] = None,
):
    messages = _build_plain_text_chat_messages(
        user_input,
        chat_history,
        system_prompt=system_prompt,
    )
    stream_filter = _ThinkTagStreamFilter()
    async for chunk in _astream_llm_with_timeout(
        llm,
        messages,
        timeout_seconds=_plain_text_chat_timeout_seconds(user_input, chat_history),
    ):
        visible = stream_filter.feed(chunk)
        if visible:
            yield visible

    tail = stream_filter.flush()
    if tail:
        yield tail


__all__ = [
    "_astream_plain_text_answer",
    "_build_plain_text_chat_messages",
    "_direct_multimodal_answer",
    "_direct_plain_text_answer",
    "_heuristic_langgraph_tool_choice",
    "_looks_like_resume_request",
    "_plain_text_chat_timeout_seconds",
    "_should_bypass_tools_for_plain_text_chat",
]
