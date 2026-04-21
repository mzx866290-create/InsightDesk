from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, HTTPException, Request


def build_session_router(
    *,
    require_remote_share_secret: Callable[[Request], None],
    current_share_link_secret: Callable[[], str],
    share_link_response_model: type,
    share_link_ttl_seconds: int,
    request_client_ip: Callable[[Request], str],
    request_user_agent: Callable[[Request], str],
    audit_security_event: Callable[..., Any],
    token_fingerprint: Callable[[str], str],
    encode_share_token: Callable[..., str],
    build_share_url: Callable[..., str],
    create_share_link_payload: Callable[..., dict[str, Any]],
    share_link_store: Any,
    workspaces_payload: Callable[..., dict[str, Any]],
    session_update_requested: Callable[..., bool],
    create_session_record: Callable[..., Any],
    reorder_sessions_payload: Callable[..., dict[str, Any]],
    deck_store: Any,
    tasks_lock: Any,
    tasks: dict[str, Any],
    suppressed_task_ids: set[str],
    prune_task_records_locked: Callable[..., None],
    get_task_store: Callable[[], Any],
    artifact_store: Any,
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

    # ── 工作区 ──────────────────────────────────

    @router.get("/api/workspaces")
    async def get_workspaces():
        from chat_store import list_workspaces
        workspaces = list_workspaces()
        return workspaces_payload(workspaces)

    @router.post("/api/workspaces")
    async def create_workspace_endpoint(request: create_workspace_request_model):
        from chat_store import create_workspace
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
        return {"ok": True, "workspace": workspace}

    @router.patch("/api/workspaces/{workspace_id}")
    async def update_workspace_endpoint(workspace_id: str, request: update_workspace_request_model):
        from chat_store import update_workspace
        field_set = request_field_set(request)
        if not field_set:
            raise HTTPException(status_code=400, detail="至少需要提供一个工作区字段")
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
            raise HTTPException(status_code=404, detail="未找到工作区")
        return {"ok": True, "workspace": workspace}

    @router.post("/api/workspaces/{workspace_id}/activate")
    async def activate_workspace_endpoint(workspace_id: str):
        from chat_store import activate_workspace
        workspace = activate_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="未找到工作区")
        return {"ok": True, "workspace": workspace}

    @router.delete("/api/workspaces/{workspace_id}")
    async def delete_workspace_endpoint(
        workspace_id: str,
        target_workspace_id: Optional[str] = None,
    ):
        from chat_store import delete_workspace
        try:
            result = delete_workspace(workspace_id, target_workspace_id=target_workspace_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="未找到工作区")
        return {"ok": True, **result}

    # ── 会话 ──────────────────────────────────

    @router.get("/api/sessions")
    async def get_sessions(
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
        return {"sessions": sessions}

    @router.post("/api/sessions")
    async def create_session(request: create_session_request_model):
        from chat_store import (
            SQLiteChatMessageHistory, connect_sqlite, get_session,
            get_workspace, update_session_meta,
        )
        try:
            return create_session_record(
                request,
                history_factory=SQLiteChatMessageHistory,
                connect_sqlite=connect_sqlite,
                get_session=get_session,
                get_workspace=get_workspace,
                update_session_meta=update_session_meta,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/api/sessions/{session_id}")
    async def update_session_endpoint(session_id: str, request: update_session_request_model):
        from chat_store import update_session_meta
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
            raise HTTPException(status_code=404, detail="会话不存在")
        return {"ok": True, "session": session}

    @router.post("/api/sessions/reorder")
    async def reorder_sessions_endpoint(request: reorder_sessions_request_model):
        from chat_store import get_all_sessions, reorder_sessions
        try:
            result = reorder_sessions(request.session_ids, workspace_id=request.workspace_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        sessions = get_all_sessions(workspace_id=request.workspace_id)
        return reorder_sessions_payload(result, sessions)

    @router.delete("/api/sessions/{session_id}")
    async def delete_session_endpoint(session_id: str):
        from chat_store import delete_session
        deck_ids = deck_store.list_ids_by_session(session_id)
        async with tasks_lock:
            stale_task_ids = [
                tid for tid, record in tasks.items()
                if str(record.session_id or "").strip() == session_id
            ]
            suppressed_task_ids.update(stale_task_ids)
            for tid in stale_task_ids:
                tasks.pop(tid, None)
            prune_task_records_locked()
        share_link_store.delete_for_resource("session", session_id)
        for deck_id in deck_ids:
            share_link_store.delete_for_resource("deck", deck_id)
        get_task_store().delete_for_session(session_id)
        artifact_store.delete_by_session(session_id)
        deck_store.delete_by_session(session_id)
        delete_session(session_id)
        return {"ok": True}

    # ── 书签 ──────────────────────────────────

    @router.get("/api/bookmarks")
    async def list_bookmarks_endpoint(session_id: Optional[str] = None):
        from chat_store import list_bookmarks
        return {"bookmarks": list_bookmarks(session_id=session_id)}

    @router.post("/api/bookmarks")
    async def create_bookmark_endpoint(request: create_bookmark_request_model):
        from chat_store import create_or_update_bookmark
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
            raise HTTPException(status_code=404, detail="未找到消息")
        return {"ok": True, "bookmark": bookmark}

    @router.delete("/api/bookmarks/{bookmark_id}")
    async def delete_bookmark_endpoint(bookmark_id: str):
        from chat_store import delete_bookmark
        ok = delete_bookmark(bookmark_id)
        if not ok:
            raise HTTPException(status_code=404, detail="未找到书签")
        return {"ok": True}

    # ── 会话分享 ──────────────────────────────────

    @router.post("/api/sessions/{session_id}/share", response_model=share_link_response_model)
    async def create_session_share_link(session_id: str, request: Request):
        import time
        from chat_store import get_session
        require_remote_share_secret(request)
        share_secret = current_share_link_secret()
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="未找到会话")
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
            expires_at=time.time() + share_link_ttl_seconds,
            created_by_ip=request_client_ip(request),
            created_user_agent=request_user_agent(request),
        )
        audit_security_event("create_session_share_link", request, details=f"session_id={session_id}")
        return share_link_response_model(**payload, expires_at=record.expires_at)

    # ── 会话消息 ──────────────────────────────────

    @router.get("/api/sessions/{session_id}/messages")
    async def get_session_messages(session_id: str):
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
        request: import_session_messages_request_model,
    ):
        from chat_store import SQLiteChatMessageHistory, replace_session_panels
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
    async def set_message_feedback_endpoint(session_id: str, request: set_message_feedback_request_model):
        from chat_store import set_message_feedback
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
            raise HTTPException(status_code=404, detail="未找到消息")
        return {"ok": True, "feedback": result}

    @router.post("/api/sessions/{session_id}/messages/truncate")
    async def truncate_session_messages_endpoint(session_id: str, request: truncate_session_messages_request_model):
        from chat_store import truncate_session_from_answer_group
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
            raise HTTPException(status_code=404, detail="未找到回答分组")
        return {"ok": True, "result": result}

    @router.delete("/api/sessions/{session_id}/messages")
    async def clear_session_messages(session_id: str):
        from agent_core import clear_session_history
        clear_session_history(session_id)
        return {"ok": True}

    # ── 检索反馈 ──────────────────────────────────

    @router.post("/api/sessions/{session_id}/retrieval-feedback")
    async def set_retrieval_feedback_endpoint(session_id: str, request: set_retrieval_feedback_request_model):
        from chat_store import set_retrieval_feedback
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
    async def list_retrieval_feedback_endpoint(session_id: str, panel_id: str, answer_group_id: str):
        from chat_store import list_retrieval_feedback
        try:
            feedback = list_retrieval_feedback(session_id, panel_id=panel_id, answer_group_id=answer_group_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"session_id": session_id, "panel_id": panel_id, "answer_group_id": answer_group_id, "feedback": feedback}

    # ── 会话记忆 ──────────────────────────────────

    @router.get("/api/sessions/{session_id}/memory")
    async def get_session_memory(session_id: str, kind: str = ""):
        from chat_store import get_session, list_session_memory
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        try:
            memories = list_session_memory(session_id, kind=kind or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            return session_memory_payload(session_id=session_id, session=session, memories=memories)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="会话记忆不存在") from exc

    @router.post("/api/sessions/{session_id}/memory/pin")
    async def pin_session_memory_endpoint(session_id: str, request: pin_session_memory_request_model):
        from chat_store import pin_session_memory
        try:
            result = pin_session_memory(session_id, content=request.content, kind=request.kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="会话不存在")
        return pin_session_memory_payload(result)

    @router.patch("/api/sessions/{session_id}/memory/{memory_id}")
    async def update_session_memory_endpoint(session_id: str, memory_id: str, request: update_session_memory_request_model):
        from chat_store import update_session_memory
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
            raise HTTPException(status_code=404, detail="未找到会话记忆") from exc

    @router.post("/api/sessions/{session_id}/memory/summarize")
    async def summarize_session_memory_endpoint(session_id: str, force: bool = False):
        from chat_store import get_session
        session = get_session(session_id)
        try:
            result = await generate_session_phase_summary_memory(session_id, trigger="manual_api", force=force)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            return summarize_session_memory_payload(session=session, result=result)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="未找到会话") from exc

    @router.delete("/api/sessions/{session_id}/memory/{memory_id}")
    async def delete_session_memory_endpoint(session_id: str, memory_id: str):
        from chat_store import delete_session_memory
        deleted = delete_session_memory(session_id, memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="会话记忆不存在")
        return delete_session_memory_payload(deleted)

    # ── 附件 & 答案分组 ──────────────────────────────────

    @router.get("/api/sessions/{session_id}/attachments")
    async def get_session_attachments(
        session_id: str,
        vector_store_path: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        from chat_store import SQLiteChatMessageHistory
        require_workspace_session(session_id, workspace_id)
        history = SQLiteChatMessageHistory(session_id=session_id)
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
        vector_store_path: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
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
        return await enqueue_task(
            tasks, tasks_lock,
            **promotion_request["enqueue_kwargs"],
            prune_in_memory=prune_task_records_locked,
            persist_record=persist_task_record,
            prune_persisted=prune_persisted_tasks,
            run_task=run_task,
            spawn_background_task=asyncio.create_task,
            logger=logger,
        )

    @router.post("/api/sessions/{session_id}/answer-groups/{answer_group_id}/promote")
    async def promote_answer_group(session_id: str, answer_group_id: str, panel_id: str):
        from chat_store import SQLiteChatMessageHistory, promote_panel_answer
        history = SQLiteChatMessageHistory(session_id=session_id)
        promoted = promote_panel_answer(session_id, answer_group_id, panel_id, db_path=history.db_path)
        if not promoted:
            raise HTTPException(status_code=404, detail="未找到回答分组或面板消息")
        return {"ok": True, **promoted}

    @router.get("/api/sessions/{session_id}/answer-groups/{answer_group_id}/review")
    async def review_answer_group(session_id: str, answer_group_id: str):
        try:
            return build_answer_group_review_payload(session_id, answer_group_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="未找到该回答分组的面板答案") from exc

    @router.post("/api/sessions/{session_id}/answer-groups/{answer_group_id}/promote/recommended")
    async def promote_recommended_answer_group(session_id: str, answer_group_id: str):
        from chat_store import SQLiteChatMessageHistory, promote_panel_answer
        try:
            review = build_answer_group_review_payload(session_id, answer_group_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="未找到该回答分组的面板答案") from exc
        panel_id = str(review.get("recommended_panel_id") or "").strip()
        history = SQLiteChatMessageHistory(session_id=session_id)
        promoted = promote_panel_answer(session_id, answer_group_id, panel_id, db_path=history.db_path)
        if not promoted:
            raise HTTPException(status_code=404, detail="未找到该回答分组的面板答案")
        return {"ok": True, "review": review, **promoted}

    @router.post("/api/sessions/{session_id}/reset")
    async def reset_session(session_id: str):
        from agent_core import clear_session_history
        from chat_store import clear_session_memory
        clear_session_history(session_id)
        clear_session_memory(session_id)
        await clear_agent_cache()
        return {"ok": True, "message": "会话已完全重置"}

    # ── 会话工件 ──────────────────────────────────

    @router.get("/api/sessions/{session_id}/artifacts")
    async def list_session_artifacts(session_id: str, artifact_type: Optional[str] = None):
        artifacts = artifact_store.list_by_session(
            session_id, artifact_type=str(artifact_type or "").strip(),
        )
        return {"artifacts": [artifact_payload(artifact) for artifact in artifacts]}

    return router
