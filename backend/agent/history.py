"""????????????????????"""

import re
import logging
from typing import Any, Optional

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, SystemMessage

logger = logging.getLogger(__name__)

CHAT_FILE_CONTEXT_START_MARKER = "[[CHAT_FILE_CONTEXT_START]]"
CHAT_FILE_CONTEXT_END_MARKER = "[[CHAT_FILE_CONTEXT_END]]"


def create_chat_message_history(session_id: str) -> BaseChatMessageHistory:
    from backend.stores.factory import create_chat_message_history as factory_create

    return factory_create(session_id=session_id)

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """
    获取或创建指定 session_id 的历史记录
    
    Args:
        session_id: 会话 ID
    
    Returns:
        该会话的历史消息存储（SQLite 持久化）
    """
    return create_chat_message_history(session_id=session_id)


def clear_session_history(session_id: str) -> bool:
    """
    清空指定 session_id 的历史记录
    
    Args:
        session_id: 会话 ID
    
    Returns:
        是否成功清空
    """
    history = create_chat_message_history(session_id=session_id)
    history.clear()
    return True


def _collapse_file_context_for_history(text: str) -> str:
    pattern = (
        re.escape(CHAT_FILE_CONTEXT_START_MARKER)
        + r"(.*?)"
        + re.escape(CHAT_FILE_CONTEXT_END_MARKER)
    )
    matches = re.findall(pattern, text or "", flags=re.DOTALL)
    if not matches:
        return (text or "").strip()

    file_names: list[str] = []
    for block in matches:
        file_names.extend(
            [
                name.strip()
                for name in re.findall(r"File name:\s*(.+)", block)
                if name.strip()
            ]
        )

    if file_names:
        display_names = "、".join(file_names[:3])
        if len(file_names) > 3:
            display_names += " 等"
        summary = f"[用户上传了 {len(file_names)} 个文件: {display_names}]"
    else:
        summary = "[用户上传了附件文件]"

    collapsed = re.sub(pattern, summary, text or "", flags=re.DOTALL).strip()
    return re.sub(r"\n{3,}", "\n\n", collapsed).strip()


def _summarize_user_input_for_history(user_input: Any) -> str:
    if isinstance(user_input, str):
        return _collapse_file_context_for_history(user_input)
    if isinstance(user_input, list):
        text_parts = []
        image_count = 0
        for item in user_input:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                text_parts.append(_collapse_file_context_for_history(str(item["text"])))
            elif item.get("type") == "image_url":
                image_count += 1
        if image_count:
            text_parts.append(f"[用户上传了 {image_count} 张图片]")
        return "\n".join(part for part in text_parts if part).strip()
    return _collapse_file_context_for_history(str(user_input))


def _preserve_system_messages_with_recent_history(
    chat_history: list[BaseMessage],
    max_recent: int = 8,
) -> list[BaseMessage]:
    if max_recent <= 0:
        return [message for message in chat_history if isinstance(message, SystemMessage)]

    non_system_messages = [
        message for message in chat_history if not isinstance(message, SystemMessage)
    ]
    keep_ids = {id(message) for message in non_system_messages[-max_recent:]}
    return [
        message
        for message in chat_history
        if isinstance(message, SystemMessage) or id(message) in keep_ids
    ]


def _trim_session_memory_content(content: str, max_chars: int = 280) -> str:
    cleaned = re.sub(r"\s+", " ", (content or "").strip())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _session_memory_kind_label(kind: str, meta: Optional[dict[str, Any]] = None) -> str:
    source = str((meta or {}).get("source") or "").strip().lower()
    if (kind or "").strip().lower() == "summary":
        return "自动阶段摘要" if source == "auto" else "阶段摘要"
    return {
        "fact": "稳定事实",
        "decision": "已确认决策",
        "todo": "后续待办",
    }.get((kind or "").strip().lower(), "长期记忆")


def _build_session_memory_message(
    memories: list[dict[str, Any]],
) -> Optional[SystemMessage]:
    normalized_memories = [
        memory for memory in memories if isinstance(memory, dict) and str(memory.get("content") or "").strip()
    ]
    if not normalized_memories:
        return None

    normalized_memories.sort(
        key=lambda memory: (
            float(memory.get("updated_at") or 0),
            float(memory.get("created_at") or 0),
            str(memory.get("id") or ""),
        )
    )

    auto_summaries: list[dict[str, Any]] = []
    manual_memories_by_kind: dict[str, list[dict[str, Any]]] = {
        "decision": [],
        "todo": [],
        "fact": [],
        "summary": [],
    }
    for memory in normalized_memories:
        kind = str(memory.get("kind") or "").strip().lower()
        meta = memory.get("meta") if isinstance(memory.get("meta"), dict) else {}
        if kind == "summary" and str(meta.get("source") or "").strip().lower() == "auto":
            auto_summaries.append(memory)
            continue
        manual_memories_by_kind.setdefault(kind or "fact", []).append(memory)

    ordered_memories: list[dict[str, Any]] = []
    ordered_memories.extend(auto_summaries[-1:])
    ordered_memories.extend(manual_memories_by_kind.get("decision", [])[-3:])
    ordered_memories.extend(manual_memories_by_kind.get("todo", [])[-3:])
    ordered_memories.extend(manual_memories_by_kind.get("fact", [])[-4:])
    ordered_memories.extend(manual_memories_by_kind.get("summary", [])[-2:])

    if not ordered_memories:
        return None

    lines = [
        "以下是当前会话沉淀出的长期记忆，包含自动阶段摘要与手动固定项。回答后续问题时请优先保持一致；如果用户明确提出变更，以最新指令为准。",
    ]
    count = 0

    for memory in ordered_memories:
        if not isinstance(memory, dict):
            continue
        content = _trim_session_memory_content(str(memory.get("content") or ""))
        if not content:
            continue
        count += 1
        meta = memory.get("meta") if isinstance(memory.get("meta"), dict) else {}
        lines.append(
            f"{count}. [{_session_memory_kind_label(str(memory.get('kind') or 'fact'), meta)}] {content}"
        )

    if count == 0:
        return None

    return SystemMessage(content="\n".join(lines))
