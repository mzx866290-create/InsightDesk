"""Content route utilities."""

import logging
import time
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from backend.routes.resource_access_helpers import (
    filter_visible_resources,
    grant_derived_resource_access,
    grant_resource_owner,
    inherit_resource_grants,
    require_resource_access,
)
from backend.helpers.deck_report_helpers import (
    attach_deck_delivery_audit,
    build_deck_delivery_response,
    update_deck_block_refs,
)
from backend.helpers.document_route_helpers import (
    document_stats_payload,
    upload_documents_result,
)
from backend.helpers.deck_route_helpers import (
    create_deck_share_link_result,
    create_deck_artifact_result,
    export_deck_response,
    grant_created_deck_artifact_access,
    regenerate_deck_slide_result,
    update_deck_block_refs_result,
    update_deck_result,
)
from backend.helpers.artifact_route_helpers import (
    generate_artifact_result,
    update_artifact_result,
)
from backend.helpers.artifact_export_route_helpers import export_artifact_response
from backend.helpers.report_route_helpers import (
    build_report_download_response,
    create_report_artifact_result,
)
from backend.helpers.resource_route_helpers import (
    artifact_for_route,
    deck_for_route,
    list_artifacts_route_payload,
    list_decks_route_payload,
)
from backend.helpers.scoped_message_route_helpers import (
    load_scoped_session_messages,
)
from backend.helpers.research_archive_route_helpers import (
    research_archives_list_payload,
    upsert_research_conflict_resolution_result,
)
from backend.helpers.share_link_route_helpers import (
    list_share_links_payload,
    open_shared_resource_response,
    revoke_share_link_result,
)
from backend.helpers.task_approval_policy_helpers import (
    load_task_approval_policy_payload,
    save_task_approval_policy_payload,
)
from backend.helpers.task_approval_route_helpers import (
    approval_decision_value,
    build_task_approval_batch_payload,
    normalize_task_approval_id,
    task_approval_batch_error_result,
    task_approval_batch_id_required_result,
    task_approval_batch_success_result,
)
from backend.helpers.workflow_task_payload_helpers import build_multi_agent_workflow_task_params
from backend.helpers.task_route_helpers import (
    apply_task_approval_decision_result,
    create_background_task_result,
    dispatch_existing_task_record_result,
    get_task_route_payload,
    list_tasks_route_payload,
    resolve_task_backend_value,
)
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
    router = APIRouter()

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
        return resolve_task_backend_value(task_backend)

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

    def load_deck_for_route(request: Request, deck_id: str, minimum_role: str) -> Any:
        return deck_for_route(
            request=request,
            deck_id=deck_id,
            minimum_role=minimum_role,
            require_deck_access=require_deck_access,
            get_deck=resolve_deck_store().get,
        )

    def load_artifact_for_route(
        request: Request,
        artifact_id: str,
        minimum_role: str,
        store: Any | None = None,
    ) -> Any:
        resolved_store = resolve_artifact_store() if store is None else store
        return artifact_for_route(
            request=request,
            artifact_id=artifact_id,
            minimum_role=minimum_role,
            require_artifact_access=require_artifact_access,
            get_artifact=resolved_store.get,
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
        return await create_background_task_result(
            http_request=http_request,
            task_type=task_type,
            params=params,
            session_id=session_id,
            on_record_created=on_record_created,
            resolve_tasks=resolve_tasks,
            tasks_lock=tasks_lock,
            enqueue_task=enqueue_task,
            prune_task_records_locked=prune_task_records_locked,
            persist_task_record=persist_task_record,
            prune_persisted_tasks=prune_persisted_tasks,
            run_task=run_task,
            logger=logger,
            task_backend=resolve_task_backend(),
            enqueue_external_task=enqueue_external_task,
            require_session_access=require_session_access,
            require_remote_editor=require_remote_editor,
            grant_derived_resource_access=grant_derived_resource_access,
            access_store=access_store,
            audit_security_event=audit_security_event,
        )

    async def dispatch_existing_task_record(record: Any) -> str:
        return await dispatch_existing_task_record_result(
            record,
            task_backend=resolve_task_backend(),
            run_task=run_task,
            enqueue_external_task=enqueue_external_task,
            logger=logger,
        )

    # Document routes

    @router.post("/api/documents/upload")
    async def upload_documents(
        request: Request,
        files: list[UploadFile] = File(...),
        vector_store_path: Optional[str] = Form(default=None),
    ):
        require_remote_editor(request)
        return await upload_documents_result(
            request=request,
            files=files,
            vector_store_path=vector_store_path,
            effective_vector_store_path=effective_vector_store_path,
            stage_upload_files=stage_upload_files,
            build_upload_documents_task_record=build_upload_documents_task_record,
            resolve_tasks=resolve_tasks,
            tasks_lock=tasks_lock,
            prune_task_records_locked=prune_task_records_locked,
            persist_task_record=persist_task_record,
            prune_persisted_tasks=prune_persisted_tasks,
            dispatch_existing_task_record=dispatch_existing_task_record,
            logger=logger,
            audit_security_event=audit_security_event,
            upload_documents_response=upload_documents_response,
            cleanup_temp_paths=cleanup_temp_paths,
            document_upload_max_count=document_upload_max_count,
            document_upload_max_file_bytes=document_upload_max_file_bytes,
            document_upload_max_total_bytes=document_upload_max_total_bytes,
        )

    @router.get("/api/documents/stats")
    async def get_document_stats(request: Request, path: Optional[str] = None):
        from backend.services.doc_pipeline import DocPipeline
        require_remote_viewer(request)
        return document_stats_payload(
            request=request,
            path=path,
            effective_vector_store_path=effective_vector_store_path,
            doc_pipeline_factory=DocPipeline,
            audit_security_event=audit_security_event,
        )

    # Task routes

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
        return await list_tasks_route_payload(
            request=request,
            limit=limit,
            status=status,
            resolve_tasks=resolve_tasks,
            tasks_lock=tasks_lock,
            prune_task_records_locked=prune_task_records_locked,
            prune_persisted_tasks=prune_persisted_tasks,
            get_task_store=get_task_store,
            task_history_limit=task_history_limit,
            require_session_access=require_session_access,
            require_remote_viewer=require_remote_viewer,
            task_backend=resolve_task_backend(),
            arq_queue_health_payload=arq_queue_health_payload,
            list_tasks_payload=list_tasks_payload,
        )

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
        return await get_task_route_payload(
            task_id=task_id,
            request=request,
            resolve_tasks=resolve_tasks,
            tasks_lock=tasks_lock,
            prune_task_records_locked=prune_task_records_locked,
            prune_persisted_tasks=prune_persisted_tasks,
            get_task_store=get_task_store,
            require_session_access=require_session_access,
            require_remote_viewer=require_remote_viewer,
            task_record_payload=task_record_payload,
        )

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
        return await apply_task_approval_decision_result(
            task_id=task_id,
            http_request=http_request,
            approval_request=request,
            resolve_tasks=resolve_tasks,
            tasks_lock=tasks_lock,
            prune_task_records_locked=prune_task_records_locked,
            prune_persisted_tasks=prune_persisted_tasks,
            get_task_store=get_task_store,
            persist_task_record=persist_task_record,
            dispatch_existing_task_record=dispatch_existing_task_record,
            require_session_access=require_session_access,
            require_remote_admin=require_remote_admin,
            audit_security_event=audit_security_event,
            task_record_payload=task_record_payload,
            now=time.time,
        )

    # Deck routes

    @router.post("/api/tasks/approvals/batch")
    async def decide_task_approvals_batch(
        http_request: Request,
        request: ApprovalTaskBatchDecisionRequest,
    ):
        results: list[dict[str, Any]] = []
        succeeded = 0
        for task_id in request.task_ids:
            normalized_task_id = normalize_task_approval_id(task_id)
            if not normalized_task_id:
                results.append(task_approval_batch_id_required_result(normalized_task_id))
                continue
            try:
                task_payload = await apply_task_approval_decision(
                    normalized_task_id,
                    http_request,
                    request,
                )
            except HTTPException as exc:
                results.append(task_approval_batch_error_result(normalized_task_id, exc.detail))
                continue
            succeeded += 1
            results.append(task_approval_batch_success_result(normalized_task_id, task_payload))

        audit_security_event(
            "task_approval_batch_decision",
            http_request,
            details=(
                f"total={len(results)} succeeded={succeeded} "
                f"failed={len(results) - succeeded} decision={approval_decision_value(request)}"
            ),
        )
        return build_task_approval_batch_payload(results, succeeded=succeeded)

    @router.post("/api/decks")
    async def create_deck(http_request: Request, request: CreateDeckRequest):
        from backend.stores.factory import create_chat_message_history
        messages = load_scoped_session_messages(
            request=http_request,
            session_id=request.session_id,
            minimum_role="editor",
            answer_group_id=request.answer_group_id,
            panel_id=request.panel_id,
            require_session_access=require_session_access,
            create_chat_message_history=create_chat_message_history,
            resolve_report_messages=resolve_report_messages_fn,
            scope_not_found_detail="Requested deck scope was not found.",
        )
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
        return list_decks_route_payload(
            request=request,
            limit=limit,
            list_recent_decks=resolve_deck_store().list_recent,
            filter_visible_resources=filter_visible_resources,
            require_remote_viewer=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
            attach_deck_delivery_audit=attach_deck_delivery_audit,
        )

    @router.get("/api/decks/{deck_id}")
    async def get_deck(deck_id: str, request: Request):
        deck = load_deck_for_route(request, deck_id, "viewer")
        return attach_deck_delivery_audit(deck).model_dump(mode="json")

    @router.patch("/api/decks/{deck_id}")
    async def update_deck(deck_id: str, http_request: Request, request: UpdateDeckRequest):
        deck = load_deck_for_route(http_request, deck_id, "editor")
        return update_deck_result(
            deck=deck,
            request=request,
            apply_deck_update=apply_deck_update,
            normalize_deck_theme=normalize_deck_theme,
            save_deck=resolve_deck_store().save,
            sync_deck_artifacts=sync_deck_artifacts,
        )

    @router.patch("/api/decks/{deck_id}/slides/{slide_id}/blocks/{block_id}/refs")
    async def update_saved_deck_block_refs(
        deck_id: str,
        slide_id: str,
        block_id: str,
        http_request: Request,
        payload: dict[str, Any],
    ):
        deck = load_deck_for_route(http_request, deck_id, "editor")
        try:
            return update_deck_block_refs_result(
                deck=deck,
                slide_id=slide_id,
                block_id=block_id,
                payload=payload,
                update_deck_block_refs=update_deck_block_refs,
                save_deck=resolve_deck_store().save,
                sync_deck_artifacts=sync_deck_artifacts,
            )
        except KeyError as exc:
            missing_id = str(exc.args[0] if exc.args else "")
            raise HTTPException(status_code=404, detail=f"Slide or block was not found: {missing_id}") from exc

    @router.post("/api/decks/{deck_id}/slides/{slide_id}/regenerate")
    async def regenerate_saved_deck_slide(
        deck_id: str, slide_id: str, http_request: Request, request: RegenerateDeckSlideRequest,
    ):
        from backend.stores.factory import create_chat_message_history
        deck = load_deck_for_route(http_request, deck_id, "editor")
        return await regenerate_deck_slide_result(
            deck=deck,
            slide_id=slide_id,
            request=request,
            create_chat_message_history=create_chat_message_history,
            resolve_report_messages=resolve_report_messages_fn,
            build_regenerate_deck_kwargs=build_regenerate_deck_kwargs,
            normalize_model_config=normalize_model_config,
            resolve_active_prompt_runtime=resolve_active_prompt_runtime,
            regenerate_deck_slide=regenerate_deck_slide,
            replace_deck_slide=replace_deck_slide,
            save_deck=resolve_deck_store().save,
            sync_deck_artifacts=sync_deck_artifacts,
            build_deck_delivery_response=build_deck_delivery_response,
        )

    @router.get("/api/decks/{deck_id}/export")
    async def export_deck(
        deck_id: str,
        request: Request,
        format: str = "pptx",
        allow_unsafe_export: bool = False,
        override_reason: str = "",
    ):
        deck = load_deck_for_route(request, deck_id, "viewer")
        return export_deck_response(
            deck=deck,
            export_format=format,
            export_deck_payload=export_deck_payload,
            export_deck_to_pptx=export_deck_to_pptx,
            build_export_filename=build_export_filename,
            build_download_content_disposition=build_download_content_disposition,
            allow_unsafe_export=allow_unsafe_export,
            override_reason=override_reason,
        )

    @router.post("/api/decks/{deck_id}/share", response_model=share_link_response_model)
    async def create_deck_share_link(deck_id: str, request: Request):
        require_remote_share_secret(request)
        load_deck_for_route(request, deck_id, "viewer")
        share_secret = current_share_link_secret()
        return create_deck_share_link_result(
            deck_id=deck_id,
            request=request,
            share_secret=share_secret,
            create_share_link_payload=create_share_link_payload_fn,
            encode_share_token=encode_share_token,
            build_share_url=build_share_url,
            share_link_store=share_link_store,
            share_link_ttl_seconds=resolve_share_link_ttl_seconds(),
            request_client_ip=request_client_ip,
            request_user_agent=request_user_agent,
            audit_security_event=audit_security_event,
            share_link_response_model=share_link_response_model,
            now=time.time,
        )

    # Report routes

    @router.post("/api/reports/generate")
    async def generate_report(http_request: Request, request: GenerateReportRequest):
        from backend.stores.factory import create_chat_message_history
        msgs = load_scoped_session_messages(
            request=http_request,
            session_id=request.session_id,
            minimum_role="editor",
            answer_group_id=request.answer_group_id,
            panel_id=request.panel_id,
            require_session_access=require_session_access,
            create_chat_message_history=create_chat_message_history,
            resolve_report_messages=resolve_report_messages_fn,
            scope_not_found_detail="Requested report scope was not found.",
        )
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
        msgs = load_scoped_session_messages(
            request=request,
            session_id=session_id,
            minimum_role="viewer",
            answer_group_id=answer_group_id,
            panel_id=panel_id,
            require_session_access=require_session_access,
            create_chat_message_history=create_chat_message_history,
            resolve_report_messages=resolve_report_messages_fn,
            scope_not_found_detail="Requested report scope was not found.",
        )
        return build_report_download_response(
            msgs,
            report_download_payload=report_download_payload,
            ensure_deckable_chat=ensure_deckable_chat,
            build_chat_report_title=build_chat_report_title,
            populate_chat_report_presentation=populate_chat_report_presentation,
            safe_report_filename=safe_report_filename,
            build_download_content_disposition=build_download_content_disposition,
        )

    # Artifact routes

    @router.get("/api/artifacts")
    async def list_artifacts(request: Request, limit: int = 100, artifact_type: str = ""):
        return list_artifacts_route_payload(
            request=request,
            limit=limit,
            artifact_type=artifact_type,
            list_recent_artifacts=resolve_artifact_store().list_recent,
            filter_visible_resources=filter_visible_resources,
            require_remote_viewer=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
            artifact_payload=artifact_payload,
        )

    @router.get("/api/research/archives")
    async def list_research_archives(
        request: Request,
        q: str = "",
        session_id: str = "",
        task_id: str = "",
        limit: int = 100,
    ):
        return research_archives_list_payload(
            request=request,
            artifacts=resolve_artifact_store().list_recent(limit=500),
            q=q,
            session_id=session_id,
            task_id=task_id,
            limit=limit,
            filter_visible_resources=filter_visible_resources,
            require_remote_viewer=require_remote_viewer,
            access_store=access_store,
            identity_store=identity_store,
        )

    @router.post("/api/research/archives/{artifact_id}/conflict-resolutions")
    async def upsert_research_conflict_resolution(
        artifact_id: str,
        request: Request,
    ):
        store = resolve_artifact_store()
        artifact = load_artifact_for_route(request, artifact_id, "editor", store)
        body = await request.json()
        return upsert_research_conflict_resolution_result(
            artifact=artifact,
            body=body,
            save_artifact=store.save,
            now=time.time,
        )

    @router.get("/api/artifacts/{artifact_id}")
    async def get_artifact(artifact_id: str, request: Request):
        artifact = load_artifact_for_route(request, artifact_id, "viewer")
        return artifact_payload(artifact)

    @router.patch("/api/artifacts/{artifact_id}")
    async def update_artifact(artifact_id: str, http_request: Request, request: UpdateArtifactRequest):
        store = resolve_artifact_store()
        artifact = load_artifact_for_route(http_request, artifact_id, "editor", store)
        return update_artifact_result(
            artifact_id=artifact_id,
            artifact=artifact,
            request=request,
            save_artifact=store.save,
            get_artifact=store.get,
            get_deck=resolve_deck_store().get,
            save_deck=resolve_deck_store().save,
            sync_deck_artifacts=sync_deck_artifacts,
            artifact_payload=artifact_payload,
        )

    @router.get("/api/artifacts/{artifact_id}/export")
    async def export_artifact(
        artifact_id: str,
        request: Request,
        format: str = "",
        allow_unsafe_export: bool = False,
        override_reason: str = "",
    ):
        store = resolve_artifact_store()
        artifact = load_artifact_for_route(request, artifact_id, "viewer", store)
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
        messages = load_scoped_session_messages(
            request=http_request,
            session_id=request.session_id,
            minimum_role="editor",
            answer_group_id=request.answer_group_id,
            panel_id=request.panel_id,
            require_session_access=require_session_access,
            create_chat_message_history=create_chat_message_history,
            resolve_report_messages=resolve_report_messages_fn,
            scope_not_found_detail="Requested artifact scope was not found.",
        )
        return await generate_artifact_result(
            http_request=http_request,
            request=request,
            messages=messages,
            create_report_artifact_result=create_report_artifact_result,
            create_deck_artifact_result=create_deck_artifact_result,
            ensure_deckable_chat=ensure_deckable_chat,
            build_chat_report_title=build_chat_report_title,
            build_report_markdown=build_report_markdown,
            build_report_artifact=build_report_artifact,
            save_artifact=resolve_artifact_store().save,
            grant_derived_resource_access=grant_derived_resource_access,
            build_deck=resolve_build_deck(),
            build_create_deck_kwargs=build_create_deck_kwargs,
            resolve_active_prompt_runtime=resolve_active_prompt_runtime,
            normalize_deck_theme=normalize_deck_theme,
            save_deck=resolve_deck_store().save,
            create_deck_artifact=create_deck_artifact_for_deck,
            grant_created_deck_artifact_access=grant_created_deck_artifact_access,
            artifact_payload=artifact_payload,
            access_store=access_store,
            require_remote_editor=require_remote_editor,
            audit_security_event=audit_security_event,
            inherit_resource_grants=inherit_resource_grants,
            grant_resource_owner=grant_resource_owner,
            now=time.time,
        )

    # Share link routes

    @router.get("/api/share-links", response_model=share_link_audit_list_response_model)
    async def list_share_links(
        request: Request,
        resource_type: str = "",
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ):
        require_remote_admin(request)
        return list_share_links_payload(
            request=request,
            resource_type=resource_type,
            active_only=active_only,
            limit=limit,
            offset=offset,
            share_link_store=share_link_store,
            share_link_audit_payload=share_link_audit_payload,
            audit_security_event=audit_security_event,
        )

    @router.delete("/api/share-links/{share_token}", response_model=revoke_share_link_response_model)
    async def revoke_share_link(share_token: str, request: Request):
        require_remote_admin(request)
        return revoke_share_link_result(
            share_token=share_token,
            request=request,
            share_link_store=share_link_store,
            token_fingerprint=token_fingerprint,
            audit_security_event=audit_security_event,
            revoke_share_link_response_model=revoke_share_link_response_model,
        )

    @router.get("/shared/{share_token}")
    async def open_shared_resource(share_token: str, request: Request):
        require_remote_share_secret(request)
        return open_shared_resource_response(
            share_token=share_token,
            request=request,
            share_secret=current_share_link_secret(),
            share_link_store=share_link_store,
            decode_share_token=decode_share_token,
            build_share_url=build_share_url,
            build_session_messages_payload=build_session_messages_payload,
            render_shared_session_html=render_shared_session_html,
            get_deck=resolve_deck_store().get,
            render_shared_deck_html=render_shared_deck_html,
            request_client_ip=request_client_ip,
            request_user_agent=request_user_agent,
            audit_security_event=audit_security_event,
            token_fingerprint=token_fingerprint,
            open_shared_resource_payload=open_shared_resource_payload,
        )

    return router

