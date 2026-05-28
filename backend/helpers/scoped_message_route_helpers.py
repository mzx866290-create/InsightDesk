"""Route-level helpers for scoped session message loading."""

from typing import Any, Callable

from fastapi import HTTPException


DEFAULT_SESSION_MESSAGES_NOT_FOUND_DETAIL = "No messages were found in this session."


def load_scoped_session_messages(
    *,
    request: Any,
    session_id: str,
    minimum_role: str,
    answer_group_id: str | None,
    panel_id: str | None,
    require_session_access: Callable[[Any, str, str], dict[str, Any]] | None,
    create_chat_message_history: Callable[..., Any],
    resolve_report_messages: Callable[..., list[Any]],
    scope_not_found_detail: str,
    empty_messages_detail: str = DEFAULT_SESSION_MESSAGES_NOT_FOUND_DETAIL,
    allow_empty: bool = False,
) -> list[Any]:
    if require_session_access is not None:
        require_session_access(request, session_id, minimum_role)
    history = create_chat_message_history(session_id=session_id)
    try:
        messages = resolve_report_messages(
            history,
            answer_group_id=answer_group_id,
            panel_id=panel_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=scope_not_found_detail) from exc
    if not messages and not allow_empty:
        raise HTTPException(status_code=400, detail=empty_messages_detail)
    return messages


__all__ = [
    "DEFAULT_SESSION_MESSAGES_NOT_FOUND_DETAIL",
    "load_scoped_session_messages",
]
