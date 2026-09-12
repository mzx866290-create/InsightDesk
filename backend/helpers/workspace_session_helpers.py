import uuid
from typing import Any, Callable


def workspaces_payload(workspaces: list[dict[str, Any]]) -> dict[str, Any]:
    active_workspace = next((item for item in workspaces if item.get("is_active")), None)
    return {
        "workspaces": workspaces,
        "active_workspace_id": (
            str(active_workspace.get("workspace_id") or "") if active_workspace else None
        ),
    }


def normalize_workspace_id(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def fallback_session_payload(
    session_id: str,
    *,
    title: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "title": title or "新对话",
        "workspace_id": workspace_id,
    }


def session_update_requested(request: Any) -> bool:
    return any(
        getattr(request, field_name, None) is not None
        for field_name in (
            "title",
            "is_archived",
            "is_favorite",
            "is_pinned",
            "tags",
            "workspace_id",
        )
    )


def reorder_sessions_payload(
    result: dict[str, Any],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": result,
        "sessions": sessions,
    }


def create_session_record(
    request: Any,
    *,
    history_factory: Callable[..., Any],
    get_session: Callable[..., dict[str, Any] | None],
    get_workspace: Callable[[str], dict[str, Any] | None],
    update_session_meta: Callable[..., Any],
    resolved_workspace_id: str | None = None,
    session_id_factory: Callable[[], Any] = uuid.uuid4,
) -> dict[str, Any]:
    requested_workspace_id = normalize_workspace_id(getattr(request, "workspace_id", None))
    target_workspace_id = requested_workspace_id or normalize_workspace_id(
        resolved_workspace_id
    )
    if target_workspace_id and not get_workspace(target_workspace_id):
        raise ValueError("工作区不存在")

    session_id = str(session_id_factory())
    history_factory(session_id=session_id)
    title = str(getattr(request, "title", "") or "").strip()

    metadata_updates: dict[str, Any] = {}
    if title:
        metadata_updates["title"] = title
    if target_workspace_id is not None:
        metadata_updates["workspace_id"] = target_workspace_id
    if metadata_updates:
        update_session_meta(
            session_id,
            **metadata_updates,
        )

    session = get_session(session_id)
    if session is None:
        return fallback_session_payload(
            session_id,
            title=title,
            workspace_id=target_workspace_id,
        )
    return session


def require_workspace_session(
    session_id: str,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    from fastapi import HTTPException

    from backend.chat_store import DEFAULT_WORKSPACE_ID, get_session, get_workspace

    normalized_session_id = str(session_id or "").strip()
    session = get_session(normalized_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    normalized_workspace_id = str(workspace_id or "").strip()
    if not normalized_workspace_id:
        return session

    if get_workspace(normalized_workspace_id) is None:
        raise HTTPException(status_code=400, detail="工作区不存在")

    session_workspace_id = str(session.get("workspace_id") or DEFAULT_WORKSPACE_ID)
    if session_workspace_id != normalized_workspace_id:
        raise HTTPException(status_code=404, detail="当前工作区中不存在该会话")

    return session
