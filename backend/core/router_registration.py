"""Router registration helpers for the FastAPI application.

The API server now builds an explicit router context before registration.  This
keeps route wiring out of the entrypoint without handing every route builder the
entire ``api_server`` module as an implicit god object.
"""

from __future__ import annotations

from typing import Any

from backend.core import (
    app_config_runtime,
    document_runtime,
    env_runtime,
    kb_runtime,
    model_config_runtime,
    prompt_runtime,
    request_runtime,
    security_runtime,
    session_summary_runtime,
)
from backend.core.runtime_metrics import (
    runtime_llm_metrics_payload,
    runtime_operations_summary_payload,
    runtime_request_metrics_payload,
)
from backend.helpers.http_runtime_helpers import build_download_content_disposition
from backend.helpers.artifact_helpers import artifact_payload as build_artifact_payload
from backend.helpers.deck_report_helpers import resolve_langchain_report_messages
from backend.helpers.identity_helpers import (
    sync_external_identity_payload as build_sync_external_identity_payload,
)
from backend.helpers.misc_helpers import request_field_set
from backend.helpers.security_helpers import (
    build_auth_whoami_payload,
    build_role_permission_matrix_payload,
    build_security_audit_action_catalog_payload,
    content_hash,
    normalize_auth_role,
    role_rank,
    share_link_audit_payload as build_share_link_audit_payload,
    token_fingerprint,
    token_preview,
)
from backend.helpers.task_runtime_helpers import (
    arq_runtime_config_for_tasks,
    build_runtime_task_summary_payload,
)
from backend.helpers.workspace_session_helpers import require_workspace_session

_registered_core_app_ids: set[int] = set()

_CORE_ROUTER_CONTEXT_ATTRIBUTES = (
    "AgentCatalogResponse", "AuthTokenCatalogResponse", "AuthWhoAmIResponse", "BACKEND_DIR", "DeleteResourceGrantRequest",
    "DeliveryTemplateCatalogResponse", "IdentityCatalogResponse", "MembershipResponse", "OrganizationResponse", "ProviderCatalogResponse",
    "ResourceAccessResponse", "ResourceGrantListResponse", "ResourceGrantResponse", "RolePermissionMatrixResponse",
    "RuntimeOperationsResponse", "SecurityAuditActionCatalogResponse", "SecurityAuditAggregateReportResponse", "SecurityAuditArchivePolicyResponse",
    "SecurityAuditCleanupResponse", "SecurityAuditEventListResponse", "SecurityAuditLegalHoldResponse", "SecurityAuditSiemExportResponse",
    "SecurityAuditSummaryResponse", "SecurityStatusResponse", "SetMembershipRequest", "SsoCallbackResponse",
    "SsoConfigResponse", "SsoLoginResponse", "SyncExternalIdentityRequest", "SyncExternalIdentityResponse",
    "PROJECT_ROOT", "TASK_BACKEND", "UpsertOrganizationRequest", "UpsertResourceGrantRequest", "UpsertUserRequest",
    "UserResponse", "_active_vector_store_id",
    "_clear_agent_cache", "_effective_sso_config_value",
    "_app_config_store", "_effective_vector_store_path", "_identity_store",
    "_resource_access_store", "_get_security_audit_store", "_integrator_scheduler_tick_lock",
    "_kb_collect_chunks", "_kb_docstore_dict", "_kb_rebuild_from_documents", "_kb_safe_metadata",
    "_persist_task_record", "_prune_persisted_tasks", "_prune_task_records_locked",
    "_run_task",
    "_runtime_metrics", "_runtime_metrics_lock", "_runtime_started_at",
    "_security_audit_events",
    "_security_status_payload", "_sso_callback_payload",
    "_sso_login_payload", "_tasks",
    "_tasks_lock", "app",
    "asyncio", "build_access_router", "build_agent_catalog_router", "build_assistant_preset_router", "build_delivery_template_router",
    "build_identity_router", "build_kb_router", "build_operations_router", "build_prompt_router",
    "build_provider_router", "build_security_router", "delete_kb_chunk_payload", "delete_kb_directory",
    "enqueue_external_task", "enqueue_task", "filter_kb_chunks",
    "install_agent_plugin_manifest_payload", "install_delivery_template_manifest_payload", "kb_health_payload", "knowledge_bases_payload", "list_agent_catalog", "list_delivery_template_catalog", "list_kb_chunks_payload", "list_llm_provider_catalog",
    "logger", "retrieval_test_payload", "time", "update_kb_chunk_payload", "arq_queue_health_payload",
    "uninstall_agent_plugin_manifest_payload", "uninstall_delivery_template_manifest_payload",
)

_DEFERRED_ROUTER_CONTEXT_ATTRIBUTES = (
    "ApprovalPolicyRequest", "ApprovalTaskDecisionRequest", "CHAT_ATTACHMENT_PREVIEW_CHARS", "CHAT_FILE_CONTEXT_END_MARKER",
    "CHAT_FILE_CONTEXT_START_MARKER", "CHAT_FILE_MAX_BYTES", "CHAT_FILE_MAX_CHARS_PER_FILE", "CHAT_FILE_MAX_COUNT",
    "CHAT_FILE_MAX_TOTAL_CHARS", "ChatFileConfig", "ChatRequest", "CreateBookmarkRequest",
    "CreateDeckRequest", "CreateMultiAgentWorkflowTaskRequest", "CreateSessionRequest", "CreateTaskRequest",
    "CreateWorkspaceRequest", "DOCUMENT_UPLOAD_MAX_COUNT", "DOCUMENT_UPLOAD_MAX_FILE_BYTES", "DOCUMENT_UPLOAD_MAX_TOTAL_BYTES",
    "DOCUMENT_UPLOAD_STAGING_DIR",
    "GenerateArtifactRequest", "GenerateReportRequest", "ImportSessionMessagesRequest", "PinSessionMemoryRequest",
    "RegenerateDeckSlideRequest", "ReorderSessionsRequest", "RevokeShareLinkResponse", "SHARE_LINK_TTL_SECONDS",
    "SUPPORTED_CHAT_FILE_EXTENSIONS", "SetMessageFeedbackRequest", "SetRetrievalFeedbackRequest", "ShareLinkAuditListResponse",
    "ShareLinkResponse", "SingleChatRequest", "TASK_BACKEND", "TASK_HISTORY_LIMIT",
    "TruncateSessionMessagesRequest", "UpdateArtifactRequest", "UpdateDeckRequest", "UpdateSessionMemoryRequest",
    "UpdateSessionRequest", "UpdateWorkspaceRequest", "_artifact_store",
    "_build_answer_group_review_payload",
    "_build_session_messages_payload", "_build_user_input_impl", "_clear_agent_cache", "_collect_session_attachments",
    "_deck_store", "_effective_vector_store_path", "_find_session_attachment",
    "_app_config_store", "_identity_store",
    "_resource_access_store", "_get_task_store", "_invoke_agent_stream",
    "_persist_task_record", "_prepare_chat_files_impl", "_prune_persisted_tasks",
    "_prune_task_records_locked", "_render_shared_deck_html", "_render_shared_session_html",
    "_run_task",
    "_session_summary_runtime_context", "_share_link_store", "_suppressed_task_ids", "_tasks",
    "_tasks_lock", "_validate_chat_payload_impl", "app",
    "apply_deck_update", "approve_runtime_mcp_connector", "arq_queue_health_payload", "artifact_export_formats",
    "attach_current_kb_status", "build_chat_report_title", "build_chat_router", "build_content_router",
    "build_create_deck_kwargs", "build_deck", "build_deck_artifact", "build_export_filename",
    "build_parallel_agent_streams", "build_regenerate_deck_kwargs", "build_report_artifact", "build_report_markdown",
    "build_session_router", "build_share_url", "build_single_agent_stream", "build_upload_documents_task_record",
    "cleanup_temp_paths", "create_session_record", "create_share_link_payload", "current_mcp_approved_connectors_payload",
    "decode_share_token", "default_mcp_server_names", "delete_session_memory_payload", "encode_share_token",
    "enqueue_external_task", "enqueue_task", "ensure_deckable_chat", "export_deck_payload",
    "export_deck_to_pptx", "get_mcp_runtime_health_history", "list_mcp_server_catalog", "list_mcp_server_runtime_health",
    "list_tasks_payload", "logger", "normalize_deck_theme", "open_shared_resource_payload",
    "persist_multi_agent_workflow_task_placeholder", "persist_web_research_task_placeholder", "pin_session_memory_payload", "populate_chat_report_presentation",
    "prepare_attachment_promotion", "prepare_chat_route_runtime", "regenerate_deck_slide", "reorder_sessions_payload",
    "replace_deck_slide", "report_download_payload", "revoke_runtime_mcp_connector", "safe_report_filename",
    "session_attachments_payload", "session_memory_payload", "session_memory_updates", "session_update_requested",
    "sse_streaming_response", "stage_upload_files", "stream_parallel_sse", "stream_single_sse",
    "summarize_session_memory_payload", "sync_deck_artifact", "task_record_payload", "time",
    "update_session_memory_payload", "upload_documents_response", "workspaces_payload",
)

_CORE_ROUTER_CONTEXT_ATTRIBUTES = tuple(
    sorted(
        set(_CORE_ROUTER_CONTEXT_ATTRIBUTES)
        | set(security_runtime.SECURITY_RUNTIME_CONTEXT_ATTRIBUTES)
    )
)
_DEFERRED_ROUTER_CONTEXT_ATTRIBUTES = tuple(
    sorted(
        set(_DEFERRED_ROUTER_CONTEXT_ATTRIBUTES)
        | set(security_runtime.SECURITY_RUNTIME_CONTEXT_ATTRIBUTES)
    )
)

_ROUTER_CONTEXT_ATTRIBUTES = tuple(
    sorted(set(_CORE_ROUTER_CONTEXT_ATTRIBUTES) | set(_DEFERRED_ROUTER_CONTEXT_ATTRIBUTES))
)


class RouterContext:
    """Whitelist-backed proxy for the API server router dependencies."""

    __slots__ = ("__router_context__", "_allowed_attributes", "_source")

    def __init__(
        self,
        source: Any,
        allowed_attributes: tuple[str, ...] = _ROUTER_CONTEXT_ATTRIBUTES,
    ) -> None:
        self.__router_context__ = True
        self._allowed_attributes = frozenset(allowed_attributes)
        self._source = source

    def __getattr__(self, name: str) -> Any:
        if name not in self._allowed_attributes:
            raise AttributeError(f"Router context has no dependency {name!r}")
        return getattr(self._source, name)


def _validate_router_context_source(
    source: Any,
    attributes: tuple[str, ...],
) -> None:
    missing = [attribute for attribute in attributes if not hasattr(source, attribute)]
    if missing:
        raise AttributeError(
            "Router context missing required attributes: " + ", ".join(missing)
        )


def build_router_context(source: Any) -> RouterContext:
    """Create the narrow dependency surface required by router registration."""
    _validate_router_context_source(source, _ROUTER_CONTEXT_ATTRIBUTES)
    return RouterContext(source, _ROUTER_CONTEXT_ATTRIBUTES)


def build_core_router_context(source: Any) -> RouterContext:
    _validate_router_context_source(source, _CORE_ROUTER_CONTEXT_ATTRIBUTES)
    return RouterContext(source, _CORE_ROUTER_CONTEXT_ATTRIBUTES)


def build_deferred_router_context(source: Any) -> RouterContext:
    _validate_router_context_source(source, _DEFERRED_ROUTER_CONTEXT_ATTRIBUTES)
    return RouterContext(source, _DEFERRED_ROUTER_CONTEXT_ATTRIBUTES)


def _ensure_router_context(
    ctx: Any,
    attributes: tuple[str, ...],
) -> RouterContext:
    if getattr(ctx, "__router_context__", False):
        missing = [
            attribute
            for attribute in attributes
            if attribute not in ctx._allowed_attributes
        ]
        if missing:
            raise AttributeError(
                "Router context missing required attributes: " + ", ".join(missing)
            )
        return ctx
    _validate_router_context_source(ctx, attributes)
    return RouterContext(ctx, attributes)


def _audit_security_event(ctx: RouterContext, *args: Any, **kwargs: Any) -> None:
    return security_runtime._audit_security_event(ctx, *args, **kwargs)


def _remote_viewer_guard(ctx: RouterContext):
    return lambda request: security_runtime._require_remote_viewer(ctx, request)


def _remote_editor_guard(ctx: RouterContext):
    return lambda request: security_runtime._require_remote_editor(ctx, request)


def _remote_admin_guard(ctx: RouterContext):
    return lambda request: security_runtime._require_remote_admin(ctx, request)


def _remote_share_secret_guard(ctx: RouterContext):
    return lambda request: security_runtime._require_remote_share_secret(ctx, request)


def _identity_store_getter(ctx: RouterContext):
    return lambda: ctx._identity_store


def _resource_access_store_getter(ctx: RouterContext):
    return lambda: ctx._resource_access_store


def _app_config_store_getter(ctx: RouterContext):
    return lambda: ctx._app_config_store


def _runtime_model_config_resolver(ctx: RouterContext):
    return lambda config: model_config_runtime.resolve_runtime_model_config(
        ctx._app_config_store,
        ctx.logger,
        config,
    )


def _deck_artifacts_syncer(ctx: RouterContext):
    def _sync_deck_artifacts(deck: Any) -> None:
        deck_id = str(getattr(deck, "deck_id", "") or "").strip()
        if not deck_id:
            return
        for artifact in ctx._artifact_store.list_by_linked_resource("deck", deck_id):
            ctx.sync_deck_artifact(artifact, deck)
            ctx._artifact_store.save(artifact)

    return _sync_deck_artifacts


def _attachment_promotion_task_getter(ctx: RouterContext):
    def _get_attachment_promotion_task(attachment_id: str, vector_store_path: str):
        attachment_id = str(attachment_id or "").strip()
        vector_store_path = str(vector_store_path or "").strip()
        if not attachment_id or not vector_store_path:
            return None
        try:
            return ctx._get_task_store().get_attachment_promotion_task(
                attachment_id,
                vector_store_path,
            )
        except Exception:
            ctx.logger.exception(
                "Failed to resolve attachment promotion state: %s -> %s",
                attachment_id,
                vector_store_path,
            )
            return None

    return _get_attachment_promotion_task


def _sync_external_identity_payload_builder(ctx: RouterContext):
    return lambda body: build_sync_external_identity_payload(
        body,
        identity_store=ctx._identity_store,
        effective_config_value=ctx._effective_sso_config_value,
        now=ctx.time.time,
    )


def _session_phase_summary_generator(ctx: RouterContext):
    async def _generate_session_phase_summary_memory(*args: Any, **kwargs: Any):
        return await session_summary_runtime._generate_session_phase_summary_memory(
            ctx._session_summary_runtime_context(),
            *args,
            **kwargs,
        )

    return _generate_session_phase_summary_memory


def _include_security_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_security_router(
            security_status_response_model=ctx.SecurityStatusResponse,
            auth_whoami_response_model=ctx.AuthWhoAmIResponse,
            auth_token_catalog_response_model=ctx.AuthTokenCatalogResponse,
            sso_config_response_model=ctx.SsoConfigResponse,
            sso_login_response_model=ctx.SsoLoginResponse,
            sso_callback_response_model=ctx.SsoCallbackResponse,
            security_audit_event_list_response_model=ctx.SecurityAuditEventListResponse,
            security_audit_cleanup_response_model=ctx.SecurityAuditCleanupResponse,
            security_audit_action_catalog_response_model=ctx.SecurityAuditActionCatalogResponse,
            security_audit_summary_response_model=ctx.SecurityAuditSummaryResponse,
            security_audit_siem_export_response_model=ctx.SecurityAuditSiemExportResponse,
            security_audit_aggregate_report_response_model=ctx.SecurityAuditAggregateReportResponse,
            security_audit_archive_policy_response_model=ctx.SecurityAuditArchivePolicyResponse,
            security_audit_legal_hold_response_model=ctx.SecurityAuditLegalHoldResponse,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            security_status_payload=lambda: ctx._security_status_payload(),
            auth_whoami_payload=lambda auth: build_auth_whoami_payload(
                auth,
                default_role="admin",
                normalize_auth_role=lambda role, **kwargs: normalize_auth_role(
                    role,
                    default=kwargs.get("default", "viewer"),
                ),
                role_rank=lambda role: role_rank(
                    role,
                    normalize_role=lambda value: normalize_auth_role(
                        value,
                        default="viewer",
                    ),
                ),
            ),
            auth_token_catalog_payload=lambda: (
                security_runtime._auth_token_catalog_payload(ctx)
            ),
            sso_config_payload=lambda: security_runtime._sso_config_payload(ctx),
            save_sso_config_payload=lambda payload: (
                security_runtime._save_sso_config_payload(ctx, payload)
            ),
            sso_login_payload=ctx._sso_login_payload,
            sso_callback_payload=ctx._sso_callback_payload,
            security_audit_events_payload=lambda **kwargs: (
                security_runtime._security_audit_events_payload(ctx, **kwargs)
            ),
            security_audit_action_catalog_payload=build_security_audit_action_catalog_payload,
            security_audit_summary_payload=lambda **kwargs: (
                security_runtime._security_audit_summary_payload(ctx, **kwargs)
            ),
            security_audit_siem_export_payload=lambda **kwargs: (
                security_runtime._security_audit_siem_export_payload(ctx, **kwargs)
            ),
            security_audit_aggregate_report_payload=lambda **kwargs: (
                security_runtime._security_audit_aggregate_report_payload(ctx, **kwargs)
            ),
            security_audit_archive_policy_payload=lambda **kwargs: (
                security_runtime._security_audit_archive_policy_payload(ctx, **kwargs)
            ),
            security_audit_legal_hold_payload=lambda **kwargs: (
                security_runtime._security_audit_legal_hold_payload(ctx, **kwargs)
            ),
            cleanup_security_audit_events=lambda **kwargs: (
                security_runtime._cleanup_security_audit_events(ctx, **kwargs)
            ),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            get_security_audit_store_count=lambda: (
                ctx._get_security_audit_store().count_events()
            ),
            get_memory_security_audit_event_count=lambda: len(
                ctx._security_audit_events
            ),
            logger=ctx.logger,
        )
    )


def _include_identity_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_identity_router(
            identity_catalog_response_model=ctx.IdentityCatalogResponse,
            organization_response_model=ctx.OrganizationResponse,
            user_response_model=ctx.UserResponse,
            membership_response_model=ctx.MembershipResponse,
            sync_external_identity_response_model=ctx.SyncExternalIdentityResponse,
            upsert_organization_request_model=ctx.UpsertOrganizationRequest,
            upsert_user_request_model=ctx.UpsertUserRequest,
            set_membership_request_model=ctx.SetMembershipRequest,
            sync_external_identity_request_model=ctx.SyncExternalIdentityRequest,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            identity_store=_identity_store_getter(ctx),
            sync_external_identity_payload=_sync_external_identity_payload_builder(ctx),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            now=ctx.time.time,
            logger=ctx.logger,
        )
    )


def _include_access_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_access_router(
            resource_grant_response_model=ctx.ResourceGrantResponse,
            resource_grant_list_response_model=ctx.ResourceGrantListResponse,
            resource_access_response_model=ctx.ResourceAccessResponse,
            role_permission_matrix_response_model=ctx.RolePermissionMatrixResponse,
            upsert_resource_grant_request_model=ctx.UpsertResourceGrantRequest,
            delete_resource_grant_request_model=ctx.DeleteResourceGrantRequest,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            access_store=_resource_access_store_getter(ctx),
            identity_store=_identity_store_getter(ctx),
            role_permission_matrix_payload=build_role_permission_matrix_payload,
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            now=ctx.time.time,
            logger=ctx.logger,
        )
    )


def _runtime_request_metrics_payload(ctx: RouterContext) -> dict[str, Any]:
    return runtime_request_metrics_payload(ctx._runtime_metrics, ctx._runtime_metrics_lock)


async def _runtime_task_summary_payload(ctx: RouterContext) -> dict[str, Any]:
    async with ctx._tasks_lock:
        records = list(ctx._tasks.values())
    return await build_runtime_task_summary_payload(
        records,
        task_backend=ctx.TASK_BACKEND,
        arq_queue_health_payload=ctx.arq_queue_health_payload,
        arq_runtime_config_for_tasks=arq_runtime_config_for_tasks,
    )


async def _runtime_operations_payload(ctx: RouterContext) -> dict[str, Any]:
    metrics = _runtime_request_metrics_payload(ctx)
    task_summary = await _runtime_task_summary_payload(ctx)
    uptime_seconds = round(max(0.0, ctx.time.time() - ctx._runtime_started_at), 3)
    llm_metrics = runtime_llm_metrics_payload()
    return {
        "started_at": ctx._runtime_started_at,
        "uptime_seconds": uptime_seconds,
        "request_metrics": {
            "total_requests": metrics["total_requests"],
            "total_errors": metrics["total_errors"],
            "by_status_class": metrics["by_status_class"],
            "last_request_at": metrics["last_request_at"],
            "last_error_at": metrics["last_error_at"],
        },
        "recent_errors": metrics["recent_errors"],
        "task_summary": task_summary,
        "operations_summary": runtime_operations_summary_payload(
            request_metrics=metrics,
            task_summary=task_summary,
            uptime_seconds=uptime_seconds,
            llm_metrics=llm_metrics,
        ),
        "security": ctx._security_status_payload(),
    }


def _include_operations_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_operations_router(
            runtime_operations_response_model=ctx.RuntimeOperationsResponse,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            runtime_request_metrics_payload=lambda: _runtime_request_metrics_payload(ctx),
            runtime_task_summary_payload=lambda: _runtime_task_summary_payload(ctx),
            runtime_operations_payload=lambda: _runtime_operations_payload(ctx),
            get_runtime_started_at=lambda: ctx._runtime_started_at,
            sync_runtime_secret_from_store=lambda env_name, config_key: (
                app_config_runtime.sync_runtime_secret_from_store(
                    _app_config_store_getter(ctx),
                    ctx.logger,
                    env_name,
                    config_key,
                )
            ),
            validate_tavily_api_key=lambda api_key: (
                app_config_runtime.validate_tavily_api_key(api_key)
            ),
            get_app_config_store=_app_config_store_getter(ctx),
            upsert_cloud_model_api_key=lambda api_key_ref, api_key: (
                app_config_runtime.upsert_cloud_model_api_key(
                    _app_config_store_getter(ctx),
                    api_key_ref,
                    api_key,
                )
            ),
            delete_cloud_model_api_key=lambda api_key_ref: (
                app_config_runtime.delete_cloud_model_api_key(
                    _app_config_store_getter(ctx),
                    api_key_ref,
                )
            ),
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            tasks=lambda: ctx._tasks,
            tasks_lock=ctx._tasks_lock,
            prune_task_records_locked=ctx._prune_task_records_locked,
            persist_task_record=ctx._persist_task_record,
            prune_persisted_tasks=ctx._prune_persisted_tasks,
            run_task=ctx._run_task,
            enqueue_task=ctx.enqueue_task,
            spawn_background_task=ctx.asyncio.create_task,
            logger=ctx.logger,
            task_backend=lambda: ctx.TASK_BACKEND,
            enqueue_external_task=ctx.enqueue_external_task,
            integrator_scheduler_tick_lock=ctx._integrator_scheduler_tick_lock,
            integrator_scheduler_config=lambda: env_runtime.integrator_scheduler_config(
                runtime_logger=ctx.logger,
            ),
        )
    )


def _include_provider_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_provider_router(
            provider_catalog_response_model=ctx.ProviderCatalogResponse,
            list_provider_catalog=ctx.list_llm_provider_catalog,
        )
    )


def _include_agent_catalog_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_agent_catalog_router(
            agent_catalog_response_model=ctx.AgentCatalogResponse,
            list_agent_catalog=ctx.list_agent_catalog,
            install_agent_plugin_manifest_payload=ctx.install_agent_plugin_manifest_payload,
            uninstall_agent_plugin_manifest_payload=ctx.uninstall_agent_plugin_manifest_payload,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
        )
    )


def _include_delivery_template_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_delivery_template_router(
            delivery_template_catalog_response_model=ctx.DeliveryTemplateCatalogResponse,
            list_delivery_template_catalog=ctx.list_delivery_template_catalog,
            install_delivery_template_manifest_payload=ctx.install_delivery_template_manifest_payload,
            uninstall_delivery_template_manifest_payload=ctx.uninstall_delivery_template_manifest_payload,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
        )
    )


def _include_assistant_preset_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_assistant_preset_router(
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_editor=_remote_editor_guard(ctx),
            list_assistant_presets=prompt_runtime.list_assistant_presets,
            create_assistant_preset=prompt_runtime.create_assistant_preset,
            update_assistant_preset=prompt_runtime.update_assistant_preset,
            delete_assistant_preset=prompt_runtime.delete_assistant_preset,
            activate_assistant_preset=prompt_runtime.activate_assistant_preset,
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            logger=ctx.logger,
        )
    )


def _include_prompt_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_prompt_router(
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_editor=_remote_editor_guard(ctx),
            list_system_prompts=prompt_runtime.list_system_prompts,
            create_system_prompt=prompt_runtime.create_system_prompt,
            update_system_prompt=prompt_runtime.update_system_prompt,
            delete_system_prompt=prompt_runtime.delete_system_prompt,
            activate_system_prompt=prompt_runtime.activate_system_prompt,
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            build_doc_pipeline=document_runtime.build_doc_pipeline,
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            logger=ctx.logger,
        )
    )


def _include_kb_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_kb_router(
            backend_dir=str(ctx.BACKEND_DIR),
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_editor=_remote_editor_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            effective_vector_store_path=lambda path: ctx._effective_vector_store_path(
                path
            ),
            resolve_project_subdir=lambda candidate: kb_runtime.resolve_project_subdir(
                candidate,
                project_root=ctx.PROJECT_ROOT,
            ),
            resolve_deletable_knowledge_base=lambda candidate: (
                kb_runtime.resolve_deletable_knowledge_base(
                    candidate,
                    project_root=ctx.PROJECT_ROOT,
                )
            ),
            active_vector_store_id=lambda: ctx._active_vector_store_id(),
            faiss_safe_store_path=lambda target_path: kb_runtime.faiss_safe_store_path(
                target_path,
                project_root=ctx.PROJECT_ROOT,
            ),
            build_doc_pipeline=document_runtime.build_doc_pipeline,
            list_kb_chunks_payload=lambda **kwargs: ctx.list_kb_chunks_payload(
                **kwargs
            ),
            update_kb_chunk_payload=lambda **kwargs: ctx.update_kb_chunk_payload(
                **kwargs
            ),
            delete_kb_chunk_payload=lambda **kwargs: ctx.delete_kb_chunk_payload(
                **kwargs
            ),
            knowledge_bases_payload=lambda **kwargs: ctx.knowledge_bases_payload(
                **kwargs
            ),
            kb_health_payload=lambda *args, **kwargs: ctx.kb_health_payload(
                *args, **kwargs
            ),
            retrieval_test_payload=lambda *args, **kwargs: ctx.retrieval_test_payload(
                *args, **kwargs
            ),
            kb_collect_chunks=lambda *args, **kwargs: ctx._kb_collect_chunks(
                *args, **kwargs
            ),
            filter_kb_chunks=lambda *args, **kwargs: ctx.filter_kb_chunks(
                *args, **kwargs
            ),
            kb_docstore_dict=lambda *args, **kwargs: ctx._kb_docstore_dict(
                *args, **kwargs
            ),
            kb_safe_metadata=lambda *args, **kwargs: ctx._kb_safe_metadata(
                *args, **kwargs
            ),
            kb_rebuild_from_documents=lambda *args, **kwargs: (
                ctx._kb_rebuild_from_documents(*args, **kwargs)
            ),
            doc_factory=document_runtime.build_langchain_document,
            delete_kb_directory=lambda *args, **kwargs: ctx.delete_kb_directory(
                *args, **kwargs
            ),
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            content_hash=content_hash,
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            logger=ctx.logger,
        )
    )


def register_core_routers(ctx) -> None:
    ctx = _ensure_router_context(ctx, _CORE_ROUTER_CONTEXT_ATTRIBUTES)
    app_id = id(ctx.app)
    if app_id in _registered_core_app_ids:
        return
    for include_router in (
        _include_security_router,
        _include_identity_router,
        _include_access_router,
        _include_operations_router,
        _include_provider_router,
        _include_agent_catalog_router,
        _include_delivery_template_router,
        _include_assistant_preset_router,
        _include_prompt_router,
        _include_kb_router,
    ):
        include_router(ctx)
    _registered_core_app_ids.add(app_id)


def _include_chat_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_chat_router(
            prepare_chat_route_runtime=ctx.prepare_chat_route_runtime,
            sse_streaming_response=ctx.sse_streaming_response,
            stream_parallel_sse=ctx.stream_parallel_sse,
            stream_single_sse=ctx.stream_single_sse,
            build_parallel_agent_streams=ctx.build_parallel_agent_streams,
            build_single_agent_stream=ctx.build_single_agent_stream,
            list_mcp_server_catalog=lambda: ctx.list_mcp_server_catalog(),
            list_mcp_server_runtime_health=lambda: ctx.list_mcp_server_runtime_health(),
            get_mcp_runtime_health_history=lambda limit: (
                ctx.get_mcp_runtime_health_history(limit)
            ),
            default_mcp_server_names=lambda: ctx.default_mcp_server_names(),
            current_mcp_approvals_payload=lambda: (
                ctx.current_mcp_approved_connectors_payload()
            ),
            approve_runtime_mcp_connector=lambda connector_name: (
                ctx.approve_runtime_mcp_connector(connector_name)
            ),
            revoke_runtime_mcp_connector=lambda connector_name: (
                ctx.revoke_runtime_mcp_connector(connector_name)
            ),
            resolve_active_prompt_runtime=prompt_runtime.resolve_active_prompt_runtime,
            validate_chat_payload=ctx._validate_chat_payload_impl,
            prepare_chat_files=lambda files: ctx._prepare_chat_files_impl(
                files,
                config=ctx.ChatFileConfig(
                    context_end_marker=ctx.CHAT_FILE_CONTEXT_END_MARKER,
                    context_start_marker=ctx.CHAT_FILE_CONTEXT_START_MARKER,
                    max_bytes=ctx.CHAT_FILE_MAX_BYTES,
                    max_chars_per_file=ctx.CHAT_FILE_MAX_CHARS_PER_FILE,
                    max_count=ctx.CHAT_FILE_MAX_COUNT,
                    max_total_chars=ctx.CHAT_FILE_MAX_TOTAL_CHARS,
                    preview_chars=ctx.CHAT_ATTACHMENT_PREVIEW_CHARS,
                    supported_extensions=frozenset(ctx.SUPPORTED_CHAT_FILE_EXTENSIONS),
                ),
                logger=ctx.logger,
            ),
            build_user_input=ctx._build_user_input_impl,
            base_model_payload=model_config_runtime.base_model_payload,
            normalize_model_config=model_config_runtime.normalize_model_config,
            model_config_payload=model_config_runtime.model_config_payload,
            invoke_agent_stream=lambda *args, **kwargs: ctx._invoke_agent_stream(
                *args, **kwargs
            ),
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            access_store=_resource_access_store_getter(ctx),
            identity_store=_identity_store_getter(ctx),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            chat_request_model=ctx.ChatRequest,
            single_chat_request_model=ctx.SingleChatRequest,
            logger=ctx.logger,
        )
    )


def _current_share_link_secret(ctx: RouterContext) -> str:
    return security_runtime._current_share_link_secret(ctx)


def _share_link_audit_payload(ctx: RouterContext, record: Any) -> dict[str, Any]:
    return build_share_link_audit_payload(
        record,
        current_time=ctx.time.time(),
        token_preview_func=token_preview,
        token_fingerprint_func=token_fingerprint,
    )


def _include_session_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_session_router(
            require_remote_share_secret=_remote_share_secret_guard(ctx),
            current_share_link_secret=lambda: _current_share_link_secret(ctx),
            share_link_response_model=ctx.ShareLinkResponse,
            share_link_ttl_seconds=lambda: ctx.SHARE_LINK_TTL_SECONDS,
            request_client_ip=request_runtime.request_client_ip,
            request_user_agent=request_runtime.request_user_agent,
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            token_fingerprint=token_fingerprint,
            encode_share_token=ctx.encode_share_token,
            build_share_url=ctx.build_share_url,
            create_share_link_payload=ctx.create_share_link_payload,
            share_link_store=ctx._share_link_store,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_editor=_remote_editor_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            access_store=_resource_access_store_getter(ctx),
            identity_store=_identity_store_getter(ctx),
            now=ctx.time.time,
            workspaces_payload=ctx.workspaces_payload,
            session_update_requested=ctx.session_update_requested,
            create_session_record=ctx.create_session_record,
            reorder_sessions_payload=ctx.reorder_sessions_payload,
            deck_store=lambda: ctx._deck_store,
            tasks_lock=ctx._tasks_lock,
            tasks=lambda: ctx._tasks,
            suppressed_task_ids=ctx._suppressed_task_ids,
            prune_task_records_locked=ctx._prune_task_records_locked,
            get_task_store=ctx._get_task_store,
            artifact_store=lambda: ctx._artifact_store,
            build_session_messages_payload=ctx._build_session_messages_payload,
            build_answer_group_review_payload=ctx._build_answer_group_review_payload,
            collect_session_attachments=ctx._collect_session_attachments,
            find_session_attachment=ctx._find_session_attachment,
            session_attachments_payload=ctx.session_attachments_payload,
            attach_current_kb_status=ctx.attach_current_kb_status,
            get_attachment_promotion_task=_attachment_promotion_task_getter(ctx),
            prepare_attachment_promotion=ctx.prepare_attachment_promotion,
            task_record_payload=ctx.task_record_payload,
            enqueue_task=ctx.enqueue_task,
            task_backend=lambda: ctx.TASK_BACKEND,
            enqueue_external_task=ctx.enqueue_external_task,
            persist_task_record=ctx._persist_task_record,
            prune_persisted_tasks=ctx._prune_persisted_tasks,
            run_task=ctx._run_task,
            session_memory_payload=ctx.session_memory_payload,
            pin_session_memory_payload=ctx.pin_session_memory_payload,
            session_memory_updates=ctx.session_memory_updates,
            update_session_memory_payload=ctx.update_session_memory_payload,
            summarize_session_memory_payload=ctx.summarize_session_memory_payload,
            delete_session_memory_payload=ctx.delete_session_memory_payload,
            generate_session_phase_summary_memory=_session_phase_summary_generator(ctx),
            validate_chat_payload=ctx._validate_chat_payload_impl,
            base_model_payload=model_config_runtime.base_model_payload,
            normalize_model_config=model_config_runtime.normalize_model_config,
            model_config_payload=model_config_runtime.model_config_payload,
            chat_attachment_preview_chars=ctx.CHAT_ATTACHMENT_PREVIEW_CHARS,
            effective_vector_store_path=lambda path=None: (
                ctx._effective_vector_store_path(path)
            ),
            require_workspace_session=require_workspace_session,
            request_field_set=request_field_set,
            artifact_payload=lambda artifact: build_artifact_payload(
                artifact,
                artifact_export_formats=ctx.artifact_export_formats,
            ),
            clear_agent_cache=ctx._clear_agent_cache,
            create_workspace_request_model=ctx.CreateWorkspaceRequest,
            update_workspace_request_model=ctx.UpdateWorkspaceRequest,
            create_session_request_model=ctx.CreateSessionRequest,
            update_session_request_model=ctx.UpdateSessionRequest,
            reorder_sessions_request_model=ctx.ReorderSessionsRequest,
            create_bookmark_request_model=ctx.CreateBookmarkRequest,
            set_message_feedback_request_model=ctx.SetMessageFeedbackRequest,
            truncate_session_messages_request_model=ctx.TruncateSessionMessagesRequest,
            import_session_messages_request_model=ctx.ImportSessionMessagesRequest,
            set_retrieval_feedback_request_model=ctx.SetRetrievalFeedbackRequest,
            pin_session_memory_request_model=ctx.PinSessionMemoryRequest,
            update_session_memory_request_model=ctx.UpdateSessionMemoryRequest,
            logger=ctx.logger,
        )
    )


def _content_external_task_enqueue(ctx: RouterContext):
    async def _enqueue_external_task(record):
        enqueue = getattr(ctx, "enqueue_external_task", None)
        if enqueue is None:
            from backend.tasks.enqueue import enqueue_arq_task

            return await enqueue_arq_task(record)
        return await enqueue(record)

    return _enqueue_external_task


def _content_stage_upload_files(ctx: RouterContext):
    async def _stage_upload_files(*args, **kwargs):
        kwargs.setdefault(
            "staging_dir",
            getattr(ctx, "DOCUMENT_UPLOAD_STAGING_DIR", None),
        )
        return await ctx.stage_upload_files(*args, **kwargs)

    return _stage_upload_files


def _include_content_router(ctx: RouterContext) -> None:
    ctx.app.include_router(
        ctx.build_content_router(
            artifact_store=lambda: ctx._artifact_store,
            deck_store=lambda: ctx._deck_store,
            share_link_store=ctx._share_link_store,
            access_store=_resource_access_store_getter(ctx),
            identity_store=_identity_store_getter(ctx),
            tasks=lambda: ctx._tasks,
            tasks_lock=ctx._tasks_lock,
            suppressed_task_ids=ctx._suppressed_task_ids,
            prune_task_records_locked=ctx._prune_task_records_locked,
            persist_task_record=ctx._persist_task_record,
            prune_persisted_tasks=ctx._prune_persisted_tasks,
            get_app_config_store=_app_config_store_getter(ctx),
            get_task_store=ctx._get_task_store,
            run_task=ctx._run_task,
            enqueue_task=ctx.enqueue_task,
            task_record_payload=ctx.task_record_payload,
            list_tasks_payload=ctx.list_tasks_payload,
            task_history_limit=ctx.TASK_HISTORY_LIMIT,
            task_backend=lambda: ctx.TASK_BACKEND,
            enqueue_external_task=_content_external_task_enqueue(ctx),
            arq_queue_health_payload=ctx.arq_queue_health_payload,
            artifact_payload=lambda artifact: build_artifact_payload(
                artifact,
                artifact_export_formats=ctx.artifact_export_formats,
            ),
            artifact_export_formats=ctx.artifact_export_formats,
            build_deck_artifact=ctx.build_deck_artifact,
            build_report_artifact=ctx.build_report_artifact,
            sync_deck_artifact=ctx.sync_deck_artifact,
            require_remote_viewer=_remote_viewer_guard(ctx),
            require_remote_editor=_remote_editor_guard(ctx),
            require_remote_admin=_remote_admin_guard(ctx),
            require_remote_share_secret=_remote_share_secret_guard(ctx),
            current_share_link_secret=lambda: _current_share_link_secret(ctx),
            audit_security_event=lambda *args, **kwargs: _audit_security_event(
                ctx, *args, **kwargs
            ),
            token_fingerprint=token_fingerprint,
            encode_share_token=ctx.encode_share_token,
            decode_share_token=ctx.decode_share_token,
            build_share_url=ctx.build_share_url,
            create_share_link_payload_fn=ctx.create_share_link_payload,
            share_link_ttl_seconds=lambda: ctx.SHARE_LINK_TTL_SECONDS,
            request_client_ip=request_runtime.request_client_ip,
            request_user_agent=request_runtime.request_user_agent,
            share_link_audit_payload=lambda record: _share_link_audit_payload(
                ctx, record
            ),
            share_link_response_model=ctx.ShareLinkResponse,
            revoke_share_link_response_model=ctx.RevokeShareLinkResponse,
            share_link_audit_list_response_model=ctx.ShareLinkAuditListResponse,
            open_shared_resource_payload=ctx.open_shared_resource_payload,
            build_session_messages_payload=ctx._build_session_messages_payload,
            render_shared_session_html=ctx._render_shared_session_html,
            render_shared_deck_html=ctx._render_shared_deck_html,
            build_download_content_disposition=build_download_content_disposition,
            build_chat_report_title=ctx.build_chat_report_title,
            build_report_markdown=ctx.build_report_markdown,
            ensure_deckable_chat=ctx.ensure_deckable_chat,
            populate_chat_report_presentation=ctx.populate_chat_report_presentation,
            safe_report_filename=ctx.safe_report_filename,
            stage_upload_files=_content_stage_upload_files(ctx),
            build_upload_documents_task_record=lambda **kwargs: (
                ctx.build_upload_documents_task_record(**kwargs)
            ),
            cleanup_temp_paths=ctx.cleanup_temp_paths,
            upload_documents_response=ctx.upload_documents_response,
            effective_vector_store_path=lambda path=None: (
                ctx._effective_vector_store_path(path)
            ),
            resolve_report_messages=resolve_langchain_report_messages,
            resolve_active_prompt_runtime=prompt_runtime.resolve_active_prompt_runtime,
            normalize_model_config=_runtime_model_config_resolver(ctx),
            build_deck=lambda **kwargs: ctx.build_deck(**kwargs),
            build_create_deck_kwargs=ctx.build_create_deck_kwargs,
            build_regenerate_deck_kwargs=lambda *args, **kwargs: (
                ctx.build_regenerate_deck_kwargs(*args, **kwargs)
            ),
            apply_deck_update=ctx.apply_deck_update,
            replace_deck_slide=ctx.replace_deck_slide,
            export_deck_payload=ctx.export_deck_payload,
            export_deck_to_pptx=ctx.export_deck_to_pptx,
            build_export_filename=ctx.build_export_filename,
            normalize_deck_theme=ctx.normalize_deck_theme,
            regenerate_deck_slide=lambda *args, **kwargs: ctx.regenerate_deck_slide(
                *args, **kwargs
            ),
            sync_deck_artifacts=_deck_artifacts_syncer(ctx),
            report_download_payload=ctx.report_download_payload,
            resolve_report_messages_fn=resolve_langchain_report_messages,
            persist_web_research_task_placeholder=ctx.persist_web_research_task_placeholder,
            persist_multi_agent_workflow_task_placeholder=(
                ctx.persist_multi_agent_workflow_task_placeholder
            ),
            document_upload_max_count=ctx.DOCUMENT_UPLOAD_MAX_COUNT,
            document_upload_max_file_bytes=ctx.DOCUMENT_UPLOAD_MAX_FILE_BYTES,
            document_upload_max_total_bytes=ctx.DOCUMENT_UPLOAD_MAX_TOTAL_BYTES,
            create_task_request_model=ctx.CreateTaskRequest,
            create_multi_agent_workflow_request_model=ctx.CreateMultiAgentWorkflowTaskRequest,
            approval_policy_request_model=ctx.ApprovalPolicyRequest,
            approval_task_decision_request_model=ctx.ApprovalTaskDecisionRequest,
            create_deck_request_model=ctx.CreateDeckRequest,
            update_deck_request_model=ctx.UpdateDeckRequest,
            regenerate_deck_slide_request_model=ctx.RegenerateDeckSlideRequest,
            generate_report_request_model=ctx.GenerateReportRequest,
            update_artifact_request_model=ctx.UpdateArtifactRequest,
            generate_artifact_request_model=ctx.GenerateArtifactRequest,
            logger=ctx.logger,
        )
    )


def register_deferred_routers(ctx) -> None:
    """Register routers that depend on late-defined helpers or request models."""
    ctx = _ensure_router_context(ctx, _DEFERRED_ROUTER_CONTEXT_ATTRIBUTES)
    for include_router in (
        _include_chat_router,
        _include_session_router,
        _include_content_router,
    ):
        include_router(ctx)
