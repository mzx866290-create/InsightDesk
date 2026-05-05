"""Session route utilities."""

import logging
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, HTTPException, Request

from backend.routes.resource_access_helpers import (
    filter_visible_resources,
    grant_resource_owner,
    require_resource_access,
)


def build_session_router(
    *,
    require_remote_share_secret: Callable[[Request], None],
    current_share_link_secret: Callable[[], str],
    share_link_response_model: type,
    share_link_ttl_seconds: int | Callable[[], int],
    request_client_ip: Callable[[Request], str],
    request_user_agent: Callable[[Request], str],
    audit_security_event: Callable[..., Any],
    token_fingerprint: Callable[[str], str],
    encode_share_token: Callable[..., str],
    build_share_url: Callable[..., str],
    create_share_link_payload: Callable[..., dict[str, Any]],
    share_link_store: Any,
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_editor: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    access_store: Any | Callable[[], Any],
    identity_store: Any | Callable[[], Any],
    now: Callable[[], float],
    workspaces_payload: Callable[..., dict[str, Any]],
    session_update_requested: Callable[..., bool],
    create_session_record: Callable[..., Any],
    reorder_sessions_payload: Callable[..., dict[str, Any]],
    deck_store: Any | Callable[[], Any],
    tasks_lock: Any,
    tasks: dict[str, Any] | Callable[[], dict[str, Any]],
    suppressed_task_ids: set[str],
    prune_task_records_locked: Callable[..., None],
    get_task_store: Callable[[], Any],
    artifact_store: Any | Callable[[], Any],
    artifact_payload: Callable[[Any], dict[str, Any]],
    build_session_messages_payload: Callable[..., dict[str, Any]],
    build_answer_group_review_payload: Callable[..., dict[str, Any]],
    collect_session_attachments: Callable[..., Any],
    find_session_attachment: Callable[..., Any],
    session_attachments_payload: Callable[..., Any],
    attach_current_kb_status: Callable[..., Any],
    get_attachment_promotion_task: Callable[..., Any],
    prepare_attachment_promotion: Callable[..., Any],
    task_record_payload: Callable[..., dict[str, Any]],
    enqueue_task: Callable[..., Any],
    task_backend: str | Callable[[], str] = "memory",
    enqueue_external_task: Callable[[Any], Awaitable[Any]] | None = None,
    persist_task_record: Callable[..., None],
    prune_persisted_tasks: Callable[[], None],
    run_task: Callable[..., Awaitable[None]],
    session_memory_payload: Callable[..., dict[str, Any]],
    pin_session_memory_payload: Callable[..., dict[str, Any]],
    session_memory_updates: Callable[..., dict[str, Any]],
    update_session_memory_payload: Callable[..., dict[str, Any]],
    summarize_session_memory_payload: Callable[..., dict[str, Any]],
    delete_session_memory_payload: Callable[..., dict[str, Any]],
    generate_session_phase_summary_memory: Callable[..., Awaitable[Optional[dict[str, Any]]]],
    validate_chat_payload: Callable[..., None],
    base_model_payload: Callable[..., dict[str, Any]],
    normalize_model_config: Callable[..., Any],
    model_config_payload: Callable[..., dict[str, Any]],
    chat_attachment_preview_chars: int,
    effective_vector_store_path: Callable[[Optional[str]], str],
    require_workspace_session: Callable[..., None],
    request_field_set: Callable[..., set[str]],
    create_workspace_request_model: type,
    update_workspace_request_model: type,
    create_session_request_model: type,
    update_session_request_model: type,
    reorder_sessions_request_model: type,
    create_bookmark_request_model: type,
    set_message_feedback_request_model: type,
    truncate_session_messages_request_model: type,
    import_session_messages_request_model: type,
    set_retrieval_feedback_request_model: type,
    pin_session_memory_request_model: type,
    update_session_memory_request_model: type,
    clear_agent_cache: Callable[[], Awaitable[None]],
    logger: logging.Logger,
) -> APIRouter:
    import asyncio

    router = APIRouter()

    def resolve_deck_store() -> Any:
        if callable(deck_store):
            return deck_store()
        return deck_store

    def resolve_artifact_store() -> Any:
        if callable(artifact_store):
            return artifact_store()
        return artifact_store

    def resolve_tasks() -> dict[str, Any]:
        if callable(tasks):
            return tasks()
        return tasks

    def resolve_task_backend() -> str:
        value = task_backend() if callable(task_backend) else task_backend
        return str(value or "memory").strip().lower() or "memory"

    def resolve_share_link_ttl_seconds() -> int:
        if callable(share_link_ttl_seconds):
            return int(share_link_ttl_seconds())
        return int(share_link_ttl_seconds)

    def require_session_access(
        request: Request, session_id: str, minimum_role: str = "viewer"
    ) -> dict[str, Any]:
        role_guard = require_remote_viewer
        if minimum_role == "editor":
            role_guard = require_remote_editor
        elif minimum_role in {"admin", "owner"}:
            role_guard = require_remote_admin
        return require_resource_access(
            request,
            resource_type="session",
            resource_id=session_id,
            minimum_role=minimum_role,
            require_remote_role=role_guard,
            access_store=access_store,
            identity_store=identity_store,
            audit_security_event=audit_security_event,
        )

    def require_workspace_access(
        request: Request, workspace_id: str, minimum_role: str = "viewer"
    ) -> dict[str, Any]:
        role_guard = require_remote_viewer
        if minimum_role == "editor":
            role_guard = require_remote_editor
        elif minimum_role in {"admin", "owner"}:
            role_guard = require_remote_admin
        return require_resource_access(
            request,
            resource_type="workspace",
            resource_id=workspace_id,
            minimum_role=minimum_role,
            require_remote_role=role_guard,
            access_store=access_store,
            identity_store=identity_store,
            audit_security_event=audit_security_event,
        )

    # 鈹€鈹€ 宸ヤ綔鍖?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/workspaces")
    async def get_workspaces(request: Request):
        from chat_store import list_workspaces
        workspaces = list_workspaces()
        visible_workspaces = filter_visible_resources(
            request,
            workspaces,
            resource_type="workspace",
            resource_id_getter=lambda item: str(item.get("workspace_id") or ""),
            require_remote_role=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
        )
        return workspaces_payload(visible_workspaces)

    @router.post("/api/workspaces")
    async def create_workspace_endpoint(http_request: Request, request: create_workspace_request_model):
        from chat_store import create_workspace
        require_remote_editor(http_request)
        try:
            preset = request.preset
            workspace = create_workspace(
                request.name,
                description=request.description,
                color=request.color,
                default_panels=[
                    base_model_payload(normalize_model_config(panel))
                    for panel in (preset.default_panels if preset else [])
                ],
                tool_config=(
                    base_model_payload(preset.tool_config)
                    if preset is not None
                    else None
                ),
                output_preset=(
                    base_model_payload(preset.output_preset)
                    if preset is not None
                    else None
                ),
                activate=request.activate,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        grant_resource_owner(
            http_request,
            resource_type="workspace",
            resource_id=str(workspace.get("workspace_id") or ""),
            require_remote_role=require_remote_editor,
            access_store=access_store,
            now=now,
            audit_security_event=audit_security_event,
        )
        return {"ok": True, "workspace": workspace}

    @router.patch("/api/workspaces/{workspace_id}")
    async def update_workspace_endpoint(workspace_id: str, http_request: Request, request: update_workspace_request_model):
        from chat_store import update_workspace
        require_workspace_access(http_request, workspace_id, "editor")
        field_set = request_field_set(request)
        if not field_set:
            raise HTTPException(status_code=400, detail="鑷冲皯闇€瑕佹彁渚涗竴涓伐浣滃尯瀛楁")
        try:
            preset = request.preset
            workspace = update_workspace(
                workspace_id,
                name=request.name if "name" in field_set else None,
                description=request.description if "description" in field_set else None,
                color=request.color if "color" in field_set else None,
                default_panels=(
                    [base_model_payload(normalize_model_config(panel)) for panel in preset.default_panels]
                    if "preset" in field_set and preset is not None
                    else None
                ),
                tool_config=(
                    base_model_payload(preset.tool_config)
                    if "preset" in field_set and preset is not None
                    else None
                ),
                output_preset=(
                    base_model_payload(preset.output_preset)
                    if "preset" in field_set and preset is not None
                    else None
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not workspace:
            raise HTTPException(status_code=404, detail="鏈壘鍒板伐浣滃尯")
        return {"ok": True, "workspace": workspace}

    @router.post("/api/workspaces/{workspace_id}/activate")
    async def activate_workspace_endpoint(workspace_id: str, request: Request):
        from chat_store import activate_workspace
        require_workspace_access(request, workspace_id, "editor")
        workspace = activate_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="鏈壘鍒板伐浣滃尯")
        return {"ok": True, "workspace": workspace}

    @router.delete("/api/workspaces/{workspace_id}")
    async def delete_workspace_endpoint(
        workspace_id: str,
        request: Request,
        target_workspace_id: Optional[str] = None,
    ):
        from chat_store import delete_workspace
        require_workspace_access(request, workspace_id, "admin")
        try:
            result = delete_workspace(workspace_id, target_workspace_id=target_workspace_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="鏈壘鍒板伐浣滃尯")
        return {"ok": True, **result}

    # 鈹€鈹€ 浼氳瘽 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/sessions")
    async def get_sessions(
        request: Request,
        query: str = "",
        archived: Optional[bool] = None,
        favorite: Optional[bool] = None,
        tag: str = "",
        workspace_id: Optional[str] = None,
    ):
        from chat_store import get_all_sessions
        sessions = get_all_sessions(
            query=query, archived=archived, favorite=favorite,
            tag=tag, workspace_id=workspace_id,
        )
        visible_sessions = filter_visible_resources(
            request,
            sessions,
            resource_type="session",
            resource_id_getter=lambda item: str(item.get("session_id") or ""),
            require_remote_role=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
        )
        return {"sessions": visible_sessions}

    @router.post("/api/sessions")
    async def create_session(http_request: Request, request: create_session_request_model):
        from chat_store import (
            SQLiteChatMessageHistory, connect_sqlite, get_session,
            get_workspace, update_session_meta,
        )
        require_remote_viewer(http_request)
        try:
            result = create_session_record(
                request,
                history_factory=SQLiteChatMessageHistory,
                connect_sqlite=connect_sqlite,
                get_session=get_session,
                get_workspace=get_workspace,
                update_session_meta=update_session_meta,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session_id = str(result.get("session", {}).get("session_id") or result.get("session_id") or "")
        if session_id:
            grant_resource_owner(
                http_request,
                resource_type="session",
                resource_id=session_id,
                require_remote_role=require_remote_viewer,
                access_store=access_store,
                now=now,
                audit_security_event=audit_security_event,
            )
        return result

    @router.patch("/api/sessions/{session_id}")
    async def update_session_endpoint(session_id: str, http_request: Request, request: update_session_request_model):
        from chat_store import update_session_meta
        require_session_access(http_request, session_id, "editor")
        if not session_update_requested(request):
            raise HTTPException(status_code=400, detail="至少需要提供一个可更新字段")
        try:
            session = update_session_meta(
                session_id,
                title=request.title,
                is_archived=request.is_archived,
                is_favorite=request.is_favorite,
                is_pinned=request.is_pinned,
                tags=request.tags,
                workspace_id=request.workspace_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not session:
            raise HTTPException(status_code=404, detail="Session was not found.")
        return {"ok": True, "session": session}

    @router.post("/api/sessions/reorder")
    async def reorder_sessions_endpoint(http_request: Request, request: reorder_sessions_request_model):
        from chat_store import get_all_sessions, reorder_sessions
        require_remote_editor(http_request)
        try:
            result = reorder_sessions(request.session_ids, workspace_id=request.workspace_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sessions = get_all_sessions(workspace_id=request.workspace_id)
        return reorder_sessions_payload(result, sessions)

    @router.delete("/api/sessions/{session_id}")
    async def delete_session_endpoint(session_id: str, request: Request):
        from chat_store import delete_session
        require_session_access(request, session_id, "admin")
        deck_ids = resolve_deck_store().list_ids_by_session(session_id)
        task_state = resolve_tasks()
        async with tasks_lock:
            stale_task_ids = [
                tid for tid, record in task_state.items()
                if str(record.session_id or "").strip() == session_id
            ]
            suppressed_task_ids.update(stale_task_ids)
            for tid in stale_task_ids:
                task_state.pop(tid, None)
            prune_task_records_locked()
        share_link_store.delete_for_resource("session", session_id)
        for deck_id in deck_ids:
            share_link_store.delete_for_resource("deck", deck_id)
        get_task_store().delete_for_session(session_id)
        resolve_artifact_store().delete_by_session(session_id)
        resolve_deck_store().delete_by_session(session_id)
        delete_session(session_id)
        return {"ok": True}

    # 鈹€鈹€ 涔︾ 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/bookmarks")
    async def list_bookmarks_endpoint(request: Request, session_id: Optional[str] = None):
        from chat_store import list_bookmarks
        bookmarks = list_bookmarks(session_id=session_id)
        if session_id:
            require_session_access(request, session_id, "viewer")
            visible_bookmarks = bookmarks
        else:
            visible_bookmarks = filter_visible_resources(
                request,
                bookmarks,
                resource_type="session",
                resource_id_getter=lambda item: str(item.get("session_id") or ""),
                require_remote_role=require_remote_viewer,
                access_store=access_store,
                identity_store=identity_store,
            )
        return {"bookmarks": visible_bookmarks}

    @router.post("/api/bookmarks")
    async def create_bookmark_endpoint(http_request: Request, request: create_bookmark_request_model):
        from chat_store import create_or_update_bookmark
        require_session_access(http_request, request.session_id, "editor")
        try:
            bookmark = create_or_update_bookmark(
                request.session_id,
                role=request.role,
                message_id=request.message_id,
                panel_id=request.panel_id,
                answer_group_id=request.answer_group_id,
                content=request.content,
                model_id=request.model_id,
                session_title=request.session_title,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not bookmark:
            raise HTTPException(status_code=404, detail="Message was not found.")
        return {"ok": True, "bookmark": bookmark}

    @router.delete("/api/bookmarks/{bookmark_id}")
    async def delete_bookmark_endpoint(bookmark_id: str, request: Request):
        from chat_store import delete_bookmark, get_bookmark
        bookmark = get_bookmark(bookmark_id)
        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark was not found.")
        require_session_access(request, str(bookmark.get("session_id") or ""), "editor")
        ok = delete_bookmark(bookmark_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Bookmark was not found.")
        return {"ok": True}

    # 鈹€鈹€ 浼氳瘽鍒嗕韩 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.post("/api/sessions/{session_id}/share", response_model=share_link_response_model)
    async def create_session_share_link(session_id: str, request: Request):
        import time
        from chat_store import get_session
        require_remote_share_secret(request)
        require_session_access(request, session_id, "viewer")
        share_secret = current_share_link_secret()
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session was not found.")
        payload = create_share_link_payload(
            "session", session_id, request,
            secret=share_secret,
            encode_share_token=encode_share_token,
            build_share_url=build_share_url,
        )
        record = share_link_store.upsert(
            share_token=payload["share_token"],
            resource_type="session",
            resource_id=session_id,
            expires_at=time.time() + resolve_share_link_ttl_seconds(),
            created_by_ip=request_client_ip(request),
            created_user_agent=request_user_agent(request),
        )
        audit_security_event("create_session_share_link", request, details=f"session_id={session_id}")
        return share_link_response_model(**payload, expires_at=record.expires_at)

    # 鈹€鈹€ 浼氳瘽娑堟伅 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/sessions/{session_id}/messages")
    async def get_session_messages(session_id: str, request: Request):
        require_session_access(request, session_id, "viewer")
        payload = build_session_messages_payload(session_id)
        return {
            "messages": payload["messages"],
            "context_limit": payload["context_limit"],
            "total_messages": payload["total_messages"],
            "panels": payload["panels"],
            "panel_messages": payload["panel_messages"],
        }

    @router.post("/api/sessions/{session_id}/messages/import")
    async def import_session_messages_endpoint(
        session_id: str,
        http_request: Request,
        request: import_session_messages_request_model,
    ):
        from chat_store import SQLiteChatMessageHistory, replace_session_panels
        require_session_access(http_request, session_id, "editor")
        # Keep SQLite here until panel import is routed through a store abstraction:
        # replace_session_panels still requires an explicit SQLite db_path.
        history = SQLiteChatMessageHistory(session_id=session_id)
        if history.get_all_message_records():
            raise HTTPException(
                status_code=400,
                detail="Session already has messages; import only supports empty sessions.",
            )
        normalized_panels: list[dict[str, Any]] = []
        panel_ids: set[str] = set()
        for panel in request.panels:
            normalized_panel = base_model_payload(normalize_model_config(panel))
            panel_id = str(normalized_panel.get("panel_id") or "").strip()
            if not panel_id:
                raise HTTPException(status_code=400, detail="Imported panels require panel_id.")
            if panel_id in panel_ids:
                raise HTTPException(status_code=400, detail="Imported panels contain duplicate panel_id.")
            panel_ids.add(panel_id)
            normalized_panels.append(normalized_panel)
        if normalized_panels:
            replace_session_panels(session_id, normalized_panels, db_path=history.db_path)
        for message in request.messages:
            images = [base_model_payload(image) for image in message.images]
            files = [base_model_payload(file) for file in message.files]
            answer_group_id = str(message.answer_group_id or "").strip()
            if message.role == "user":
                history.add_user_message(message.content, answer_group_id=answer_group_id, images=images, files=files)
                continue
            panel_id = str(message.panel_id or "").strip()
            if not panel_id:
                raise HTTPException(status_code=400, detail="Imported assistant messages require panel_id.")
            if panel_ids and panel_id not in panel_ids:
                raise HTTPException(status_code=400, detail="Imported assistant message references an unknown panel_id.")
            history.add_ai_message(
                message.content,
                model_id=str(message.model_id or "").strip(),
                panel_id=panel_id,
                answer_group_id=answer_group_id,
                images=images,
                files=files,
                sources=[dict(item) for item in message.sources if isinstance(item, dict)],
                workflow_nodes=[dict(item) for item in message.workflow_nodes if isinstance(item, dict)],
                task_id=str(message.task_id or "").strip(),
                task_type=str(message.task_type or "").strip(),
            )
        payload = build_session_messages_payload(session_id)
        return {
            "messages": payload["messages"],
            "context_limit": payload["context_limit"],
            "total_messages": payload["total_messages"],
            "panels": payload["panels"],
            "panel_messages": payload["panel_messages"],
        }

    @router.post("/api/sessions/{session_id}/messages/feedback")
    async def set_message_feedback_endpoint(session_id: str, http_request: Request, request: set_message_feedback_request_model):
        from chat_store import set_message_feedback
        require_session_access(http_request, session_id, "editor")
        try:
            result = set_message_feedback(
                session_id,
                feedback_value=request.value,
                message_id=request.message_id,
                panel_id=request.panel_id,
                answer_group_id=request.answer_group_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="Message was not found.")
        return {"ok": True, "feedback": result}

    @router.post("/api/sessions/{session_id}/messages/truncate")
    async def truncate_session_messages_endpoint(session_id: str, http_request: Request, request: truncate_session_messages_request_model):
        from chat_store import truncate_session_from_answer_group
        require_session_access(http_request, session_id, "editor")
        validate_chat_payload(request.content, request.images, request.files)
        try:
            result = truncate_session_from_answer_group(
                session_id,
                answer_group_id=request.answer_group_id,
                content=request.content,
                images=[base_model_payload(image) for image in request.images],
                files=[base_model_payload(file) for file in request.files],
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="Answer group was not found.")
        return {"ok": True, "result": result}

    @router.delete("/api/sessions/{session_id}/messages")
    async def clear_session_messages(session_id: str, request: Request):
        from backend.services.agent_core import clear_session_history
        require_session_access(request, session_id, "admin")
        clear_session_history(session_id)
        return {"ok": True}

    # 鈹€鈹€ 妫€绱㈠弽棣?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.post("/api/sessions/{session_id}/retrieval-feedback")
    async def set_retrieval_feedback_endpoint(session_id: str, http_request: Request, request: set_retrieval_feedback_request_model):
        from chat_store import set_retrieval_feedback
        require_session_access(http_request, session_id, "editor")
        try:
            result = set_retrieval_feedback(
                session_id,
                panel_id=request.panel_id,
                answer_group_id=request.answer_group_id,
                source=request.source,
                feedback_value=request.value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "feedback": result}

    @router.get("/api/sessions/{session_id}/retrieval-feedback")
    async def list_retrieval_feedback_endpoint(session_id: str, request: Request, panel_id: str, answer_group_id: str):
        from chat_store import list_retrieval_feedback
        require_session_access(request, session_id, "viewer")
        try:
            feedback = list_retrieval_feedback(session_id, panel_id=panel_id, answer_group_id=answer_group_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"session_id": session_id, "panel_id": panel_id, "answer_group_id": answer_group_id, "feedback": feedback}

    # 鈹€鈹€ 浼氳瘽璁板繂 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/sessions/{session_id}/memory")
    async def get_session_memory(session_id: str, request: Request, kind: str = ""):
        from chat_store import get_session, list_session_memory
        require_session_access(request, session_id, "viewer")
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session was not found.")
        try:
            memories = list_session_memory(session_id, kind=kind or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            return session_memory_payload(session_id=session_id, session=session, memories=memories)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session memory was not found.") from exc

    @router.post("/api/sessions/{session_id}/memory/pin")
    async def pin_session_memory_endpoint(session_id: str, http_request: Request, request: pin_session_memory_request_model):
        from chat_store import pin_session_memory
        require_session_access(http_request, session_id, "editor")
        try:
            result = pin_session_memory(session_id, content=request.content, kind=request.kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="Session was not found.")
        return pin_session_memory_payload(result)

    @router.patch("/api/sessions/{session_id}/memory/{memory_id}")
    async def update_session_memory_endpoint(session_id: str, memory_id: str, http_request: Request, request: update_session_memory_request_model):
        from chat_store import update_session_memory
        require_session_access(http_request, session_id, "editor")
        try:
            updates = session_memory_updates(request, field_set=request_field_set(request))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            memory = update_session_memory(session_id, memory_id, **updates)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            return update_session_memory_payload(memory)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session memory was not found.") from exc

    @router.post("/api/sessions/{session_id}/memory/summarize")
    async def summarize_session_memory_endpoint(session_id: str, request: Request, force: bool = False):
        from chat_store import get_session
        require_session_access(request, session_id, "editor")
        session = get_session(session_id)
        try:
            result = await generate_session_phase_summary_memory(session_id, trigger="manual_api", force=force)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            return summarize_session_memory_payload(session=session, result=result)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session was not found.") from exc

    @router.delete("/api/sessions/{session_id}/memory/{memory_id}")
    async def delete_session_memory_endpoint(session_id: str, memory_id: str, request: Request):
        from chat_store import delete_session_memory
        require_session_access(request, session_id, "editor")
        deleted = delete_session_memory(session_id, memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session memory was not found.")
        return delete_session_memory_payload(deleted)

    # 鈹€鈹€ 闄勪欢 & 绛旀鍒嗙粍 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/sessions/{session_id}/attachments")
    async def get_session_attachments(
        session_id: str,
        request: Request,
        vector_store_path: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        from backend.stores.factory import create_chat_message_history
        require_session_access(request, session_id, "viewer")
        require_workspace_session(session_id, workspace_id)
        history = create_chat_message_history(session_id=session_id)
        return session_attachments_payload(
            session_id=session_id,
            message_records=history.get_all_message_records(),
            preview_char_limit=chat_attachment_preview_chars,
            vector_store_path=effective_vector_store_path(vector_store_path),
            collect_attachments=collect_session_attachments,
            attach_current_kb_status=attach_current_kb_status,
            lookup_task=get_attachment_promotion_task,
        )

    @router.post("/api/sessions/{session_id}/attachments/{attachment_id}/promote")
    async def promote_session_attachment_to_kb(
        session_id: str,
        attachment_id: str,
        request: Request,
        vector_store_path: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        require_session_access(request, session_id, "editor")
        require_workspace_session(session_id, workspace_id)
        attachment = find_session_attachment(
            session_id, attachment_id,
            preview_char_limit=chat_attachment_preview_chars,
        )
        target_vector_store_path = effective_vector_store_path(vector_store_path)
        try:
            promotion_request = prepare_attachment_promotion(
                session_id=session_id,
                attachment_id=attachment_id,
                attachment=attachment,
                target_vector_store_path=target_vector_store_path,
                workspace_id=workspace_id,
                existing_task=get_attachment_promotion_task(attachment_id, target_vector_store_path),
                task_record_payload=task_record_payload,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if promotion_request["dedupe_payload"] is not None:
            return promotion_request["dedupe_payload"]
        task_state = resolve_tasks()
        return await enqueue_task(
            task_state, tasks_lock,
            **promotion_request["enqueue_kwargs"],
            prune_in_memory=prune_task_records_locked,
            persist_record=persist_task_record,
            prune_persisted=prune_persisted_tasks,
            run_task=run_task,
            spawn_background_task=asyncio.create_task,
            logger=logger,
            task_backend=resolve_task_backend(),
            enqueue_external_task=enqueue_external_task,
        )

    @router.post("/api/sessions/{session_id}/answer-groups/{answer_group_id}/promote")
    async def promote_answer_group(session_id: str, answer_group_id: str, request: Request, panel_id: str):
        from chat_store import SQLiteChatMessageHistory, promote_panel_answer
        from backend.helpers.session_helpers import record_answer_preference_signal
        require_session_access(request, session_id, "editor")
        review: dict[str, Any] | None = None
        try:
            review = build_answer_group_review_payload(session_id, answer_group_id)
        except KeyError:
            review = None
        # Keep SQLite here because promote_panel_answer still updates SQLite rows by db_path.
        history = SQLiteChatMessageHistory(session_id=session_id)
        promoted = promote_panel_answer(session_id, answer_group_id, panel_id, db_path=history.db_path)
        if not promoted:
            raise HTTPException(status_code=404, detail="鏈壘鍒板洖绛斿垎缁勬垨闈㈡澘娑堟伅")
        preference_signal = (
            record_answer_preference_signal(
                session_id,
                answer_group_id,
                panel_id,
                review,
            )
            if review is not None
            else {}
        )
        return {"ok": True, "preference_signal": preference_signal, **promoted}

    @router.get("/api/sessions/{session_id}/answer-groups/{answer_group_id}/review")
    async def review_answer_group(session_id: str, answer_group_id: str, request: Request):
        require_session_access(request, session_id, "viewer")
        try:
            return build_answer_group_review_payload(session_id, answer_group_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Answer group review target was not found.") from exc

    @router.post("/api/sessions/{session_id}/answer-groups/{answer_group_id}/promote/recommended")
    async def promote_recommended_answer_group(session_id: str, answer_group_id: str, request: Request):
        from chat_store import SQLiteChatMessageHistory, promote_panel_answer
        from backend.helpers.session_helpers import record_answer_preference_signal
        require_session_access(request, session_id, "editor")
        try:
            review = build_answer_group_review_payload(session_id, answer_group_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Answer group review target was not found.") from exc
        panel_id = str(review.get("recommended_panel_id") or "").strip()
        # Keep SQLite here because promote_panel_answer still updates SQLite rows by db_path.
        history = SQLiteChatMessageHistory(session_id=session_id)
        promoted = promote_panel_answer(session_id, answer_group_id, panel_id, db_path=history.db_path)
        if not promoted:
            raise HTTPException(status_code=404, detail="Answer group review target was not found.")
        preference_signal = record_answer_preference_signal(
            session_id,
            answer_group_id,
            panel_id,
            review,
        )
        return {"ok": True, "review": review, "preference_signal": preference_signal, **promoted}

    @router.post("/api/sessions/{session_id}/reset")
    async def reset_session(session_id: str, request: Request):
        from backend.services.agent_core import clear_session_history
        from chat_store import clear_session_memory
        require_session_access(request, session_id, "admin")
        clear_session_history(session_id)
        clear_session_memory(session_id)
        await clear_agent_cache()
        return {"ok": True, "message": "Session has been fully reset."}

    # 鈹€鈹€ 浼氳瘽宸ヤ欢 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/sessions/{session_id}/artifacts")
    async def list_session_artifacts(session_id: str, request: Request, artifact_type: Optional[str] = None):
        require_session_access(request, session_id, "viewer")
        artifacts = resolve_artifact_store().list_by_session(
            session_id, artifact_type=str(artifact_type or "").strip(),
        )
        return {"artifacts": [artifact_payload(artifact) for artifact in artifacts]}

    return router

