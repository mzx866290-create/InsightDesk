"""Content route utilities."""

import logging
import time
from typing import Any, Awaitable, Callable, Coroutine, Optional, cast

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from backend.routes.resource_access_helpers import (
    filter_visible_resources,
    grant_derived_resource_access,
    grant_resource_owner,
    inherit_resource_grants,
    require_resource_access,
)
from backend.helpers.deck_report_helpers import (
    DeckExportGateError,
    attach_deck_delivery_audit,
    build_deck_delivery_response,
    update_deck_block_refs,
)
from backend.helpers.deck_route_helpers import (
    create_deck_artifact_result,
    grant_created_deck_artifact_access,
)
from backend.helpers.artifact_export_route_helpers import export_artifact_response
from backend.helpers.report_route_helpers import (
    build_report_download_response,
    create_report_artifact_result,
)
from backend.helpers.research_archive_helpers import (
    artifact_content,
    compact_text,
    is_research_archive_artifact,
    matches_research_archive_filters,
    research_archive_payload,
    research_conflict_groups,
    research_conflict_review_records,
)
from backend.helpers.task_approval_policy_helpers import (
    load_task_approval_policy_payload,
    save_task_approval_policy_payload,
)
from backend.helpers.workflow_task_payload_helpers import build_multi_agent_workflow_task_params
from backend.schemas.api_models import (
    ApprovalPolicyRequest,
    ApprovalTaskBatchDecisionRequest,
    ApprovalTaskDecisionRequest,
    CreateDeckRequest,
    CreateMultiAgentWorkflowTaskRequest,
    CreateTaskRequest,
    GenerateArtifactRequest,
    GenerateReportRequest,
    RegenerateDeckSlideRequest,
    UpdateArtifactRequest,
    UpdateDeckRequest,
)
from backend.tasks.backends import dispatch_task_record


def build_content_router(
    *,
    artifact_store: Any | Callable[[], Any],
    deck_store: Any | Callable[[], Any],
    share_link_store: Any,
    access_store: Any | Callable[[], Any],
    identity_store: Any | Callable[[], Any],
    tasks: dict[str, Any] | Callable[[], dict[str, Any]],
    tasks_lock: Any,
    suppressed_task_ids: set[str],
    prune_task_records_locked: Callable[..., None],
    persist_task_record: Callable[..., None],
    prune_persisted_tasks: Callable[[], None],
    get_app_config_store: Callable[[], Any],
    get_task_store: Callable[[], Any],
    run_task: Callable[..., Awaitable[None]],
    enqueue_task: Callable[..., Any],
    task_record_payload: Callable[..., dict[str, Any]],
    list_tasks_payload: Callable[..., dict[str, Any]],
    task_history_limit: int,
    artifact_payload: Callable[[Any], dict[str, Any]],
    artifact_export_formats: Callable[[Any], list[str]],
    build_deck_artifact: Callable[..., Any],
    build_report_artifact: Callable[..., Any],
    sync_deck_artifact: Callable[..., None],
    require_remote_viewer: Callable[[Request], dict[str, Any]],
    require_remote_editor: Callable[[Request], dict[str, Any]],
    require_remote_admin: Callable[[Request], dict[str, Any]],
    require_remote_share_secret: Callable[[Request], None],
    current_share_link_secret: Callable[[], str],
    audit_security_event: Callable[..., Any],
    token_fingerprint: Callable[[str], str],
    encode_share_token: Callable[..., str],
    decode_share_token: Callable[..., tuple[str, str]],
    build_share_url: Callable[..., str],
    create_share_link_payload_fn: Callable[..., dict[str, Any]],
    share_link_ttl_seconds: int | Callable[[], int],
    request_client_ip: Callable[[Request], str],
    request_user_agent: Callable[[Request], str],
    share_link_audit_payload: Callable[[Any], dict[str, Any]],
    share_link_response_model: type,
    revoke_share_link_response_model: type,
    share_link_audit_list_response_model: type,
    open_shared_resource_payload: Callable[..., dict[str, Any]],
    build_session_messages_payload: Callable[..., dict[str, Any]],
    render_shared_session_html: Callable[..., Any],
    render_shared_deck_html: Callable[..., Any],
    build_download_content_disposition: Callable[[str], str],
    build_chat_report_title: Callable[..., str],
    build_report_markdown: Callable[..., str],
    ensure_deckable_chat: Callable[..., Any],
    populate_chat_report_presentation: Callable[..., None],
    safe_report_filename: Callable[[str], str],
    stage_upload_files: Callable[..., Awaitable[Any]],
    build_upload_documents_task_record: Callable[..., Any],
    cleanup_temp_paths: Callable[..., None],
    upload_documents_response: Callable[..., dict[str, Any]],
    effective_vector_store_path: Callable[[Optional[str]], str],
    resolve_report_messages: Callable[..., list[Any]],
    resolve_active_prompt_runtime: Callable[..., Any],
    normalize_model_config: Callable[..., Any],
    build_deck: Callable[..., Awaitable[Any]],
    build_create_deck_kwargs: Callable[..., dict[str, Any]],
    build_regenerate_deck_kwargs: Callable[..., dict[str, Any]],
    apply_deck_update: Callable[..., None],
    replace_deck_slide: Callable[..., None],
    export_deck_payload: Callable[..., dict[str, Any]],
    export_deck_to_pptx: Callable[..., Any],
    build_export_filename: Callable[..., str],
    normalize_deck_theme: Callable[..., str],
    regenerate_deck_slide: Callable[..., Awaitable[Any]],
    sync_deck_artifacts: Callable[..., None],
    report_download_payload: Callable[..., dict[str, Any]],
    resolve_report_messages_fn: Callable[..., list[Any]],
    persist_web_research_task_placeholder: Callable[..., None],
    persist_multi_agent_workflow_task_placeholder: Callable[..., None],
    document_upload_max_count: int,
    document_upload_max_file_bytes: int,
    document_upload_max_total_bytes: int,
    create_task_request_model: type,
    create_multi_agent_workflow_request_model: type,
    approval_policy_request_model: type,
    approval_task_decision_request_model: type,
    create_deck_request_model: type,
    update_deck_request_model: type,
    regenerate_deck_slide_request_model: type,
    generate_report_request_model: type,
    update_artifact_request_model: type,
    generate_artifact_request_model: type,
    logger: logging.Logger,
    task_backend: str | Callable[[], str] = "memory",
    enqueue_external_task: Callable[[Any], Awaitable[Any]] | None = None,
    arq_queue_health_payload: Callable[[], Awaitable[dict[str, Any]]] | None = None,
) -> APIRouter:
    import asyncio

    router = APIRouter()

    def spawn_background_task(coro: Awaitable[None]) -> Any:
        return asyncio.create_task(cast(Coroutine[Any, Any, None], coro))

    def resolve_artifact_store() -> Any:
        if callable(artifact_store):
            return artifact_store()
        return artifact_store

    def resolve_deck_store() -> Any:
        if callable(deck_store):
            return deck_store()
        return deck_store

    def resolve_tasks() -> dict[str, Any]:
        if callable(tasks):
            return tasks()
        return tasks

    def resolve_task_backend() -> str:
        value = task_backend() if callable(task_backend) else task_backend
        return str(value or "memory").strip().lower() or "memory"

    def resolve_build_deck() -> Callable[..., Awaitable[Any]]:
        return build_deck

    def resolve_share_link_ttl_seconds() -> int:
        if callable(share_link_ttl_seconds):
            return int(share_link_ttl_seconds())
        return int(share_link_ttl_seconds)

    def approval_policy_payload() -> dict[str, Any]:
        return load_task_approval_policy_payload(get_app_config_store(), logger)

    def save_approval_policy_payload(raw_policy: Any) -> dict[str, Any]:
        return save_task_approval_policy_payload(get_app_config_store(), raw_policy)

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

    def require_deck_access(
        request: Request, deck_id: str, minimum_role: str = "viewer"
    ) -> dict[str, Any]:
        role_guard = require_remote_viewer
        if minimum_role == "editor":
            role_guard = require_remote_editor
        elif minimum_role in {"admin", "owner"}:
            role_guard = require_remote_admin
        return require_resource_access(
            request,
            resource_type="deck",
            resource_id=deck_id,
            minimum_role=minimum_role,
            require_remote_role=role_guard,
            access_store=access_store,
            identity_store=identity_store,
            audit_security_event=audit_security_event,
        )

    def require_artifact_access(
        request: Request, artifact_id: str, minimum_role: str = "viewer"
    ) -> dict[str, Any]:
        role_guard = require_remote_viewer
        if minimum_role == "editor":
            role_guard = require_remote_editor
        elif minimum_role in {"admin", "owner"}:
            role_guard = require_remote_admin
        return require_resource_access(
            request,
            resource_type="artifact",
            resource_id=artifact_id,
            minimum_role=minimum_role,
            require_remote_role=role_guard,
            access_store=access_store,
            identity_store=identity_store,
            audit_security_event=audit_security_event,
        )

    def create_deck_artifact_for_deck(deck: Any) -> Any:
        artifact = build_deck_artifact(deck)
        resolve_artifact_store().save(artifact)
        return artifact

    async def create_background_task_payload(
        *,
        http_request: Request,
        task_type: str,
        params: dict[str, Any],
        session_id: str | None = None,
        on_record_created: Callable[..., None] | None = None,
    ) -> dict[str, Any]:
        if session_id:
            require_session_access(http_request, session_id, "editor")
        else:
            require_remote_editor(http_request)
        task_state = resolve_tasks()
        payload: dict[str, Any] = await enqueue_task(
            task_state,
            tasks_lock,
            task_type=task_type,
            params=params,
            session_id=session_id,
            prune_in_memory=prune_task_records_locked,
            persist_record=persist_task_record,
            prune_persisted=prune_persisted_tasks,
            run_task=run_task,
            spawn_background_task=spawn_background_task,
            logger=logger,
            task_backend=resolve_task_backend(),
            enqueue_external_task=enqueue_external_task,
            on_record_created=on_record_created,
        )
        if session_id and payload.get("task_id"):
            grant_derived_resource_access(
                http_request,
                source_resource_type="session",
                source_resource_id=session_id,
                target_resource_type="task",
                target_resource_id=str(payload.get("task_id") or ""),
                access_store=access_store,
                require_remote_role=require_remote_editor,
                now=time.time,
                audit_security_event=audit_security_event,
            )
        return payload

    async def dispatch_existing_task_record(record: Any) -> str:
        backend = await dispatch_task_record(
            record,
            task_backend=resolve_task_backend(),
            run_task=run_task,
            spawn_background_task=spawn_background_task,
            enqueue_external_task=enqueue_external_task,
        )
        logger.info(
            "task_id=%s task_type=%s dispatched backend=%s",
            getattr(record, "task_id", ""),
            getattr(record, "task_type", ""),
            backend,
        )
        return backend

    # 鈹€鈹€ 鏂囨。绠＄悊 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.post("/api/documents/upload")
    async def upload_documents(
        request: Request,
        files: list[UploadFile] = File(...),
        vector_store_path: Optional[str] = Form(default=None),
    ):
        require_remote_editor(request)
        temp_paths: list[str] = []
        try:
            evsp = effective_vector_store_path(vector_store_path)
            temp_paths, file_names = await stage_upload_files(
                files,
                max_file_count=document_upload_max_count,
                max_file_bytes=document_upload_max_file_bytes,
                max_total_bytes=document_upload_max_total_bytes,
            )
            record = build_upload_documents_task_record(
                temp_paths=temp_paths,
                file_names=file_names,
                vector_store_path=evsp,
            )
            task_state = resolve_tasks()
            async with tasks_lock:
                task_state[record.task_id] = record
                prune_task_records_locked(record.created_at)
            persist_task_record(record)
            prune_persisted_tasks()
            await dispatch_existing_task_record(record)
            logger.info("task_id=%s task_type=upload_documents created", record.task_id)
            audit_security_event(
                "upload_documents", request,
                details=f"file_count={len(file_names)} vector_store_path={evsp}",
            )
            return upload_documents_response(record, file_count=len(file_names), vector_store_path=evsp)
        except ValueError as e:
            if temp_paths:
                cleanup_temp_paths(temp_paths)
            audit_security_event("upload_documents", request, result="rejected", details=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            if temp_paths:
                cleanup_temp_paths(temp_paths)
            logger.exception("Document upload failed")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/documents/stats")
    async def get_document_stats(request: Request, path: Optional[str] = None):
        from backend.services.doc_pipeline import DocPipeline
        require_remote_viewer(request)
        pipeline = DocPipeline(vector_store_path=effective_vector_store_path(path))
        try:
            pipeline.load_store()
            stats = pipeline.get_stats()
            stats.setdefault("store_path", pipeline.vector_store_path)
            audit_security_event("get_document_stats", request, details=f"path={pipeline.vector_store_path}")
            return stats
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 鈹€鈹€ 寮傛浠诲姟 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.post("/api/tasks")
    async def create_task(http_request: Request, request: CreateTaskRequest):
        on_record_created = None
        if request.task_type == "web_research":
            on_record_created = persist_web_research_task_placeholder
        elif request.task_type == "multi_agent_workflow":
            on_record_created = persist_multi_agent_workflow_task_placeholder
        return await create_background_task_payload(
            http_request=http_request,
            task_type=request.task_type,
            params=request.params,
            session_id=request.session_id,
            on_record_created=on_record_created,
        )

    @router.post("/api/tasks/multi-agent-workflow")
    async def create_multi_agent_workflow_task(
        http_request: Request,
        request: CreateMultiAgentWorkflowTaskRequest,
    ):
        try:
            params = build_multi_agent_workflow_task_params(
                request,
                task_approval_policy_loader=approval_policy_payload,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return await create_background_task_payload(
            http_request=http_request,
            task_type="multi_agent_workflow",
            params=params,
            session_id=request.session_id,
            on_record_created=persist_multi_agent_workflow_task_placeholder,
        )

    @router.get("/api/tasks")
    async def list_tasks(request: Request, limit: int = 20, status: str = ""):
        task_state = resolve_tasks()
        async with tasks_lock:
            prune_task_records_locked()
            in_memory_tasks = list(task_state.values())
        prune_persisted_tasks()
        persisted_tasks = get_task_store().list_recent(limit=max(limit, task_history_limit))
        filtered_in_memory_tasks = []
        for record in in_memory_tasks:
            if getattr(record, "session_id", None):
                try:
                    require_session_access(request, str(record.session_id), "viewer")
                except HTTPException as exc:
                    if exc.status_code == 403:
                        continue
                    raise
            else:
                require_remote_viewer(request)
            filtered_in_memory_tasks.append(record)
        filtered_persisted_tasks = []
        for record in persisted_tasks:
            if getattr(record, "session_id", None):
                try:
                    require_session_access(request, str(record.session_id), "viewer")
                except HTTPException as exc:
                    if exc.status_code == 403:
                        continue
                    raise
            else:
                require_remote_viewer(request)
            filtered_persisted_tasks.append(record)
        queue_health = None
        if resolve_task_backend() in {"arq", "redis"} and arq_queue_health_payload is not None:
            queue_health = await arq_queue_health_payload()
        payload = list_tasks_payload(
            in_memory_tasks=filtered_in_memory_tasks,
            persisted_tasks=filtered_persisted_tasks,
            limit=limit,
            status_filter=status,
            queue_health=queue_health,
        )
        return payload

    @router.get("/api/tasks/approval-policy")
    async def get_task_approval_policy(request: Request):
        require_remote_admin(request)
        return approval_policy_payload()

    @router.put("/api/tasks/approval-policy")
    async def update_task_approval_policy(
        http_request: Request,
        request: ApprovalPolicyRequest,
    ):
        require_remote_admin(http_request)
        payload = save_approval_policy_payload(request)
        audit_security_event(
            "task_approval_policy_update",
            http_request,
            details=(
                f"enabled={payload['enabled']} "
                f"required_task_types={len(payload['required_task_types'])} "
                f"high_risk_requires_approval={payload['high_risk_requires_approval']} "
                f"default_reviewer_role={payload['default_reviewer_role']}"
            ),
        )
        return payload

    @router.get("/api/tasks/{task_id}")
    async def get_task(task_id: str, request: Request):
        task_state = resolve_tasks()
        async with tasks_lock:
            prune_task_records_locked()
            record = task_state.get(task_id)
        if record is None:
            prune_persisted_tasks()
            record = get_task_store().get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task was not found.")
        if getattr(record, "session_id", None):
            require_session_access(request, str(record.session_id), "viewer")
        else:
            require_remote_viewer(request)
        return task_record_payload(record)

    @router.post("/api/tasks/{task_id}/approval")
    async def decide_task_approval(
        task_id: str,
        http_request: Request,
        request: ApprovalTaskDecisionRequest,
    ):
        return await apply_task_approval_decision(task_id, http_request, request)

    async def apply_task_approval_decision(
        task_id: str,
        http_request: Request,
        request: Any,
    ) -> dict[str, Any]:
        task_state = resolve_tasks()
        async with tasks_lock:
            prune_task_records_locked()
            record = task_state.get(task_id)
        if record is None:
            prune_persisted_tasks()
            record = get_task_store().get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task was not found.")
        if record.task_type != "multi_agent_workflow":
            raise HTTPException(status_code=400, detail="Task does not support approval decisions.")
        if record.status != getattr(type(record.status), "WAITING_APPROVAL", record.status):
            if str(getattr(record.status, "value", record.status)) != "waiting_approval":
                raise HTTPException(status_code=400, detail="Task is not waiting for approval.")
        if getattr(record, "session_id", None):
            require_session_access(http_request, str(record.session_id), "editor")
        else:
            require_remote_admin(http_request)

        params = dict(record.params or {})
        params["approval_decision"] = str(request.decision or "").strip().lower()
        params["approval_reviewer"] = str(request.reviewer or "").strip()
        params["approval_comment"] = str(request.comment or "").strip()
        record.params = params
        record.status = getattr(type(record.status), "PENDING", record.status)
        record.progress = min(100, max(10, int(getattr(record, "progress", 0) or 0)))
        record.error = None
        record.result = ""
        record.updated_at = time.time()

        async with tasks_lock:
            task_state[task_id] = record
            prune_task_records_locked(record.updated_at)
        persist_task_record(record)
        prune_persisted_tasks()
        await dispatch_existing_task_record(record)
        audit_security_event(
            "task_approval_decision",
            http_request,
            details=(
                f"task_id={task_id} decision={params['approval_decision']} "
                f"session_id={getattr(record, 'session_id', '') or '<none>'}"
            ),
        )
        return task_record_payload(record)

    # 鈹€鈹€ 婕旂ず绋?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.post("/api/tasks/approvals/batch")
    async def decide_task_approvals_batch(
        http_request: Request,
        request: ApprovalTaskBatchDecisionRequest,
    ):
        results: list[dict[str, Any]] = []
        succeeded = 0
        for task_id in request.task_ids:
            normalized_task_id = str(task_id or "").strip()
            if not normalized_task_id:
                results.append(
                    {"task_id": normalized_task_id, "ok": False, "error": "Task id is required."}
                )
                continue
            try:
                task_payload = await apply_task_approval_decision(
                    normalized_task_id,
                    http_request,
                    request,
                )
            except HTTPException as exc:
                results.append(
                    {
                        "task_id": normalized_task_id,
                        "ok": False,
                        "error": str(exc.detail),
                    }
                )
                continue
            succeeded += 1
            results.append(
                {
                    "task_id": normalized_task_id,
                    "ok": True,
                    "task": task_payload,
                }
            )

        failed = len(results) - succeeded
        audit_security_event(
            "task_approval_batch_decision",
            http_request,
            details=(
                f"total={len(results)} succeeded={succeeded} failed={failed} "
                f"decision={str(request.decision or '').strip().lower()}"
            ),
        )
        return {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    @router.post("/api/decks")
    async def create_deck(http_request: Request, request: CreateDeckRequest):
        from backend.stores.factory import create_chat_message_history
        require_session_access(http_request, request.session_id, "editor")
        history = create_chat_message_history(session_id=request.session_id)
        try:
            messages = resolve_report_messages_fn(
                history, answer_group_id=request.answer_group_id, panel_id=request.panel_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Requested deck scope was not found.") from exc
        if not messages:
            raise HTTPException(status_code=400, detail="No messages were found in this session.")
        try:
            created = await create_deck_artifact_result(
                request=request,
                messages=messages,
                build_deck=resolve_build_deck(),
                build_create_deck_kwargs=build_create_deck_kwargs,
                resolve_active_prompt_runtime=resolve_active_prompt_runtime,
                normalize_deck_theme=normalize_deck_theme,
                save_deck=resolve_deck_store().save,
                create_deck_artifact=create_deck_artifact_for_deck,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        grant_created_deck_artifact_access(
            request=http_request,
            session_id=request.session_id,
            deck_id=created.deck_id,
            artifact_id=created.artifact_id,
            access_store=access_store,
            require_remote_editor=require_remote_editor,
            audit_security_event=audit_security_event,
            inherit_resource_grants=inherit_resource_grants,
            grant_resource_owner=grant_resource_owner,
            now=time.time,
        )
        return created.deck_payload

    @router.get("/api/decks")
    async def list_decks(request: Request, limit: int = 100):
        safe_limit = max(1, min(500, int(limit or 100)))
        decks = resolve_deck_store().list_recent(limit=safe_limit)
        visible_decks = filter_visible_resources(
            request,
            decks,
            resource_type="deck",
            resource_id_getter=lambda deck: str(getattr(deck, "deck_id", "") or ""),
            require_remote_role=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
        )
        return {
            "decks": [
                attach_deck_delivery_audit(deck).model_dump(mode="json")
                for deck in visible_decks
            ],
            "total": len(visible_decks),
            "limit": safe_limit,
        }

    @router.get("/api/decks/{deck_id}")
    async def get_deck(deck_id: str, request: Request):
        require_deck_access(request, deck_id, "viewer")
        try:
            deck = resolve_deck_store().get(deck_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Deck was not found.") from exc
        return attach_deck_delivery_audit(deck).model_dump(mode="json")

    @router.patch("/api/decks/{deck_id}")
    async def update_deck(deck_id: str, http_request: Request, request: UpdateDeckRequest):
        require_deck_access(http_request, deck_id, "editor")
        try:
            deck = resolve_deck_store().get(deck_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Deck was not found.") from exc
        if request.slides is not None and not request.slides:
            raise HTTPException(status_code=400, detail="Deck must keep at least one slide.")
        apply_deck_update(deck, request, normalize_deck_theme=normalize_deck_theme)
        resolve_deck_store().save(deck)
        sync_deck_artifacts(deck)
        return deck.model_dump(mode="json")

    @router.patch("/api/decks/{deck_id}/slides/{slide_id}/blocks/{block_id}/refs")
    async def update_saved_deck_block_refs(
        deck_id: str,
        slide_id: str,
        block_id: str,
        http_request: Request,
        payload: dict[str, Any],
    ):
        require_deck_access(http_request, deck_id, "editor")
        try:
            deck = resolve_deck_store().get(deck_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Deck was not found.") from exc
        try:
            result = update_deck_block_refs(deck, slide_id, block_id, payload)
        except KeyError as exc:
            missing_id = str(exc.args[0] if exc.args else "")
            raise HTTPException(status_code=404, detail=f"Slide or block was not found: {missing_id}") from exc
        resolve_deck_store().save(deck)
        sync_deck_artifacts(deck)
        block = result["block"]
        return {
            "deck": deck.model_dump(mode="json"),
            "slide_id": result["slide_id"],
            "block_id": result["block_id"],
            "block": block.model_dump(mode="json") if hasattr(block, "model_dump") else block,
            "citation_validation": result["citation_validation"],
            "evidence_review": result["evidence_review"],
            "export_gate": result["export_gate"],
            "slide_delivery": result["slide_delivery"],
        }

    @router.post("/api/decks/{deck_id}/slides/{slide_id}/regenerate")
    async def regenerate_saved_deck_slide(
        deck_id: str, slide_id: str, http_request: Request, request: RegenerateDeckSlideRequest,
    ):
        from backend.stores.factory import create_chat_message_history
        require_deck_access(http_request, deck_id, "editor")
        try:
            deck = resolve_deck_store().get(deck_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Deck was not found.") from exc
        history = create_chat_message_history(session_id=deck.meta.session_id)
        try:
            messages = resolve_report_messages_fn(
                history,
                answer_group_id=getattr(deck.meta, "source_answer_group_id", None),
                panel_id=getattr(deck.meta, "source_panel_id", None),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Requested deck scope was not found.") from exc
        if not messages:
            raise HTTPException(status_code=400, detail="No messages were found in this session.")
        regenerate_kwargs = build_regenerate_deck_kwargs(
            deck, request,
            normalize_model_config=normalize_model_config,
            resolve_active_prompt_runtime=resolve_active_prompt_runtime,
        )
        try:
            regenerated_slide = await regenerate_deck_slide(deck=deck, slide_id=slide_id, messages=messages, **regenerate_kwargs)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Slide was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        replace_deck_slide(deck, regenerated_slide)
        resolve_deck_store().save(deck)
        sync_deck_artifacts(deck)
        return build_deck_delivery_response(deck, focus_slide_id=slide_id)

    @router.get("/api/decks/{deck_id}/export")
    async def export_deck(
        deck_id: str,
        request: Request,
        format: str = "pptx",
        allow_unsafe_export: bool = False,
        override_reason: str = "",
    ):
        require_deck_access(request, deck_id, "viewer")
        if format != "pptx":
            raise HTTPException(status_code=400, detail="褰撳墠浠呮敮鎸佸鍑?PPTX")
        try:
            deck = resolve_deck_store().get(deck_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Deck was not found.") from exc
        try:
            ep = export_deck_payload(
                deck,
                export_deck_to_pptx=export_deck_to_pptx,
                build_export_filename=build_export_filename,
                allow_unsafe_export=allow_unsafe_export,
                override_reason=override_reason,
            )
        except DeckExportGateError as exc:
            raise HTTPException(status_code=409, detail=exc.payload) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return Response(
            content=ep["content"],
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": build_download_content_disposition(ep["filename"])},
        )

    @router.post("/api/decks/{deck_id}/share", response_model=share_link_response_model)
    async def create_deck_share_link(deck_id: str, request: Request):
        require_remote_share_secret(request)
        require_deck_access(request, deck_id, "viewer")
        share_secret = current_share_link_secret()
        try:
            resolve_deck_store().get(deck_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="鏈壘鍒版紨绀虹") from exc
        payload = create_share_link_payload_fn(
            "deck", deck_id, request,
            secret=share_secret,
            encode_share_token=encode_share_token,
            build_share_url=build_share_url,
        )
        record = share_link_store.upsert(
            share_token=payload["share_token"],
            resource_type="deck",
            resource_id=deck_id,
            expires_at=time.time() + resolve_share_link_ttl_seconds(),
            created_by_ip=request_client_ip(request),
            created_user_agent=request_user_agent(request),
        )
        audit_security_event("create_deck_share_link", request, details=f"deck_id={deck_id}")
        return share_link_response_model(**payload, expires_at=record.expires_at)

    # 鈹€鈹€ 鎶ュ憡 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.post("/api/reports/generate")
    async def generate_report(http_request: Request, request: GenerateReportRequest):
        from backend.stores.factory import create_chat_message_history
        require_session_access(http_request, request.session_id, "editor")
        history = create_chat_message_history(session_id=request.session_id)
        try:
            msgs = resolve_report_messages_fn(history, answer_group_id=request.answer_group_id, panel_id=request.panel_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Requested report scope was not found.") from exc
        if not msgs:
            raise HTTPException(status_code=400, detail="No messages were found in this session.")
        try:
            report_created = create_report_artifact_result(
                request=request,
                messages=msgs,
                ensure_deckable_chat=ensure_deckable_chat,
                build_chat_report_title=build_chat_report_title,
                build_report_markdown=build_report_markdown,
                build_report_artifact=build_report_artifact,
                save_artifact=resolve_artifact_store().save,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        grant_derived_resource_access(
            http_request,
            source_resource_type="session",
            source_resource_id=request.session_id,
            target_resource_type="artifact",
            target_resource_id=report_created.artifact_id,
            access_store=access_store,
            require_remote_role=require_remote_editor,
            now=time.time,
            audit_security_event=audit_security_event,
        )
        return {
            "markdown": report_created.markdown,
            "title": report_created.title,
            "artifact_id": report_created.artifact_id,
        }

    @router.get("/api/reports/download/{session_id}")
    async def download_report_pptx(
        session_id: str,
        request: Request,
        answer_group_id: Optional[str] = None,
        panel_id: Optional[str] = None,
    ):
        from backend.stores.factory import create_chat_message_history
        require_session_access(request, session_id, "viewer")
        history = create_chat_message_history(session_id=session_id)
        try:
            msgs = resolve_report_messages_fn(history, answer_group_id=answer_group_id, panel_id=panel_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Requested report scope was not found.") from exc
        return build_report_download_response(
            msgs,
            report_download_payload=report_download_payload,
            ensure_deckable_chat=ensure_deckable_chat,
            build_chat_report_title=build_chat_report_title,
            populate_chat_report_presentation=populate_chat_report_presentation,
            safe_report_filename=safe_report_filename,
            build_download_content_disposition=build_download_content_disposition,
        )

    # 鈹€鈹€ Artifacts 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/artifacts")
    async def list_artifacts(request: Request, limit: int = 100, artifact_type: str = ""):
        safe_limit = max(1, min(500, int(limit or 100)))
        artifacts = resolve_artifact_store().list_recent(
            limit=safe_limit,
            artifact_type=artifact_type,
        )
        visible_artifacts = filter_visible_resources(
            request,
            artifacts,
            resource_type="artifact",
            resource_id_getter=lambda artifact: str(getattr(artifact, "artifact_id", "") or ""),
            require_remote_role=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
        )
        return {
            "artifacts": [artifact_payload(artifact) for artifact in visible_artifacts],
            "total": len(visible_artifacts),
            "limit": safe_limit,
        }

    @router.get("/api/research/archives")
    async def list_research_archives(
        request: Request,
        q: str = "",
        session_id: str = "",
        task_id: str = "",
        limit: int = 100,
    ):
        safe_limit = max(1, min(500, int(limit or 100)))
        query_text = str(q or "").strip()
        session_filter = str(session_id or "").strip()
        task_filter = str(task_id or "").strip()
        artifacts = [
            artifact
            for artifact in resolve_artifact_store().list_recent(limit=500)
            if is_research_archive_artifact(artifact)
            and matches_research_archive_filters(
                artifact,
                q=query_text,
                session_id=session_filter,
                task_id=task_filter,
            )
        ]
        visible_artifacts = filter_visible_resources(
            request,
            artifacts,
            resource_type="artifact",
            resource_id_getter=lambda artifact: str(getattr(artifact, "artifact_id", "") or ""),
            require_remote_role=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
        )
        limited_artifacts = visible_artifacts[:safe_limit]
        return {
            "archives": [
                research_archive_payload(artifact)
                for artifact in limited_artifacts
            ],
            "conflict_groups": research_conflict_groups(visible_artifacts),
            "total": len(visible_artifacts),
            "limit": safe_limit,
        }

    @router.post("/api/research/archives/{artifact_id}/conflict-resolutions")
    async def upsert_research_conflict_resolution(
        artifact_id: str,
        request: Request,
    ):
        require_artifact_access(request, artifact_id, "editor")
        store = resolve_artifact_store()
        try:
            artifact = store.get(artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Artifact was not found.") from exc
        if not is_research_archive_artifact(artifact):
            raise HTTPException(status_code=400, detail="Artifact is not a research archive.")

        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Resolution payload must be an object.")
        conflict_id = str(body.get("conflict_id") or "").strip()
        claim_id = str(body.get("claim_id") or "").strip()
        if not conflict_id and not claim_id:
            raise HTTPException(status_code=400, detail="conflict_id or claim_id is required.")
        status = str(body.get("status") or "resolved").strip() or "resolved"
        if status not in {"resolved", "dismissed", "needs_followup", "reviewed"}:
            raise HTTPException(status_code=400, detail="Unsupported resolution status.")

        content = artifact_content(artifact)
        records = research_conflict_review_records(content)
        record = {
            "conflict_id": conflict_id or claim_id,
            "claim_id": claim_id,
            "status": status,
            "resolution": compact_text(body.get("resolution"), 1000),
            "note": compact_text(body.get("note"), 1000),
            "reviewer": compact_text(body.get("reviewer"), 120),
            "updated_at": time.time(),
        }
        replaced = False
        for index, existing in enumerate(records):
            if (
                str(existing.get("conflict_id") or "") == record["conflict_id"]
                or (
                    record["claim_id"]
                    and str(existing.get("claim_id") or "") == record["claim_id"]
                )
            ):
                records[index] = record
                replaced = True
                break
        if not replaced:
            records.append(record)
        content["conflict_review_resolutions"] = records
        artifact.content = content
        store.save(artifact)
        return {
            "resolution": record,
            "archive": research_archive_payload(artifact),
        }

    @router.get("/api/artifacts/{artifact_id}")
    async def get_artifact(artifact_id: str, request: Request):
        require_artifact_access(request, artifact_id, "viewer")
        store = resolve_artifact_store()
        try:
            artifact = store.get(artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Artifact was not found.") from exc
        return artifact_payload(artifact)

    @router.patch("/api/artifacts/{artifact_id}")
    async def update_artifact(artifact_id: str, http_request: Request, request: UpdateArtifactRequest):
        require_artifact_access(http_request, artifact_id, "editor")
        store = resolve_artifact_store()
        try:
            artifact = store.get(artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Artifact was not found.") from exc
        next_title = str(request.title or "").strip()
        if artifact.artifact_type == "report":
            if next_title:
                artifact.title = next_title
            if request.markdown is not None:
                artifact.content["markdown"] = str(request.markdown or "").strip()
            store.save(artifact)
            return artifact_payload(artifact)
        if artifact.artifact_type == "deck":
            if request.markdown is not None:
                raise HTTPException(status_code=400, detail="Deck artifact does not support markdown patching.")
            deck_id = str(artifact.linked_resource_id or artifact.content.get("deck_id") or "").strip()
            if not deck_id:
                raise HTTPException(status_code=400, detail="Deck artifact is missing deck_id.")
            try:
                deck = resolve_deck_store().get(deck_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Deck was not found.") from exc
            if next_title:
                deck.meta.title = next_title
                if deck.slides and deck.slides[0].type == "cover":
                    deck.slides[0].title = next_title
                resolve_deck_store().save(deck)
            sync_deck_artifacts(deck)
            return artifact_payload(store.get(artifact_id))
        raise HTTPException(status_code=400, detail="Unsupported artifact type.")

    @router.get("/api/artifacts/{artifact_id}/export")
    async def export_artifact(
        artifact_id: str,
        request: Request,
        format: str = "",
        allow_unsafe_export: bool = False,
        override_reason: str = "",
    ):
        require_artifact_access(request, artifact_id, "viewer")
        store = resolve_artifact_store()
        try:
            artifact = store.get(artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Artifact was not found.") from exc
        return export_artifact_response(
            artifact=artifact,
            export_format=format,
            get_deck=resolve_deck_store().get,
            export_deck_payload=export_deck_payload,
            export_deck_to_pptx=export_deck_to_pptx,
            build_export_filename=build_export_filename,
            build_download_content_disposition=build_download_content_disposition,
            safe_report_filename=safe_report_filename,
            populate_chat_report_presentation=populate_chat_report_presentation,
            allow_unsafe_export=allow_unsafe_export,
            override_reason=override_reason,
        )

    @router.post("/api/artifacts/generate")
    async def generate_artifact(http_request: Request, request: GenerateArtifactRequest):
        from backend.stores.factory import create_chat_message_history
        require_session_access(http_request, request.session_id, "editor")
        history = create_chat_message_history(session_id=request.session_id)
        try:
            messages = resolve_report_messages_fn(history, answer_group_id=request.answer_group_id, panel_id=request.panel_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Requested artifact scope was not found.") from exc
        if not messages:
            raise HTTPException(status_code=400, detail="No usable messages were found for artifact generation.")
        if request.artifact_type == "report":
            try:
                report_created = create_report_artifact_result(
                    request=request,
                    messages=messages,
                    ensure_deckable_chat=ensure_deckable_chat,
                    build_chat_report_title=build_chat_report_title,
                    build_report_markdown=build_report_markdown,
                    build_report_artifact=build_report_artifact,
                    save_artifact=resolve_artifact_store().save,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            grant_derived_resource_access(
                http_request,
                source_resource_type="session",
                source_resource_id=request.session_id,
                target_resource_type="artifact",
                target_resource_id=report_created.artifact_id,
                access_store=access_store,
                require_remote_role=require_remote_editor,
                now=time.time,
                audit_security_event=audit_security_event,
            )
            return artifact_payload(report_created.artifact)
        if request.artifact_type == "deck":
            if request.panel_config is None:
                raise HTTPException(status_code=400, detail="Deck artifact requires panel_config.")
            try:
                deck_created = await create_deck_artifact_result(
                    request=request,
                    messages=messages,
                    build_deck=resolve_build_deck(),
                    build_create_deck_kwargs=build_create_deck_kwargs,
                    resolve_active_prompt_runtime=resolve_active_prompt_runtime,
                    normalize_deck_theme=normalize_deck_theme,
                    save_deck=resolve_deck_store().save,
                    create_deck_artifact=create_deck_artifact_for_deck,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            grant_created_deck_artifact_access(
                request=http_request,
                session_id=request.session_id,
                deck_id=deck_created.deck_id,
                artifact_id=deck_created.artifact_id,
                access_store=access_store,
                require_remote_editor=require_remote_editor,
                audit_security_event=audit_security_event,
                inherit_resource_grants=inherit_resource_grants,
                grant_resource_owner=grant_resource_owner,
                now=time.time,
            )
            return artifact_payload(deck_created.artifact)
        raise HTTPException(status_code=400, detail="Unsupported artifact type.")

    # 鈹€鈹€ 鍒嗕韩閾炬帴 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    @router.get("/api/share-links", response_model=share_link_audit_list_response_model)
    async def list_share_links(
        request: Request,
        resource_type: str = "",
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ):
        require_remote_admin(request)
        records = share_link_store.list_links(resource_type=resource_type, active_only=active_only, limit=limit, offset=offset)
        payload_records = [share_link_audit_payload(record) for record in records]
        payload = {
            "share_links": payload_records,
            "total": len(payload_records),
            "active_count": sum(1 for item in payload_records if item["is_active"]),
        }
        audit_security_event(
            "list_share_links", request,
            details=f"resource_type={resource_type or '<all>'} active_only={active_only} total={payload['total']}",
        )
        return payload

    @router.delete("/api/share-links/{share_token}", response_model=revoke_share_link_response_model)
    async def revoke_share_link(share_token: str, request: Request):
        require_remote_admin(request)
        if not share_link_store.revoke(share_token):
            raise HTTPException(status_code=404, detail="Share link was not found.")
        audit_security_event("revoke_share_link", request, details=f"share_token_fp={token_fingerprint(share_token)}")
        return revoke_share_link_response_model(ok=True)

    @router.get("/shared/{share_token}")
    async def open_shared_resource(share_token: str, request: Request):
        require_remote_share_secret(request)
        share_secret = current_share_link_secret()
        try:
            link_record = share_link_store.get_active(share_token)
            if link_record is None:
                raise ValueError("鍒嗕韩閾炬帴涓嶅瓨鍦ㄣ€佸凡杩囨湡鎴栧凡鎾ら攢")
            decoded_type, decoded_id = decode_share_token(share_token, share_secret)
            if link_record.resource_type != decoded_type or link_record.resource_id != decoded_id:
                raise ValueError("鍒嗕韩閾炬帴鏃犳晥")
            shared_payload = open_shared_resource_payload(
                share_token, request,
                secret=share_secret,
                decode_share_token=decode_share_token,
                build_share_url=build_share_url,
                build_session_messages_payload=build_session_messages_payload,
                render_shared_session_html=render_shared_session_html,
                get_deck=resolve_deck_store().get,
                render_shared_deck_html=render_shared_deck_html,
            )
            share_link_store.record_access(
                share_token,
                accessed_ip=request_client_ip(request),
                accessed_user_agent=request_user_agent(request),
            )
            audit_security_event(
                "open_shared_resource", request,
                details=f"resource_type={decoded_type} share_token_fp={token_fingerprint(share_token)}",
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            detail = str(exc.args[0]) if exc.args else "Not found"
            raise HTTPException(status_code=404, detail=detail) from exc
        return Response(content=shared_payload["content"], media_type=shared_payload["media_type"])

    return router

