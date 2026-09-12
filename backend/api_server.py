"""
FastAPI 后端 API 服务
提供 REST + SSE 端点，包装现有 agent_core / chat_store / doc_pipeline 模块
"""

import asyncio
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.agent.connection import list_llm_provider_catalog
from backend.agent.registry import (
    install_agent_plugin_manifest_payload,
    list_agent_catalog,
    uninstall_agent_plugin_manifest_payload,
)
from backend.agent_mcp_helpers import (
    current_mcp_approved_connectors_payload as _current_mcp_approved_connectors_payload,
)
from backend.agent_mcp_helpers import (
    default_mcp_server_names,
    list_mcp_server_catalog,
)
from backend.agent_mcp_helpers import (
    get_mcp_runtime_health_history as _get_mcp_runtime_health_history,
)
from backend.agent_mcp_helpers import (
    list_mcp_server_runtime_health as _list_mcp_server_runtime_health,
)
from backend.agent_mcp_helpers import (
    set_runtime_mcp_approved_connectors as _set_runtime_mcp_approved_connectors,
)
from backend.core import agent_stream_runtime
from backend.core import (
    env_runtime,
    prompt_runtime,
    rate_limit,
    request_runtime,
    security_runtime,
    session_summary_runtime,
    sso_runtime,
    task_runtime,
)
from backend.core import mcp_runtime as mcp_runtime_helpers
from backend.core.app_lifecycle import register_app_lifecycle_handler
from backend.core.config_runtime import (
    sync_runtime_secret_from_store,
)
from backend.core.router_registration import (
    _CORE_ROUTER_CONTEXT_ATTRIBUTES,
    _DEFERRED_ROUTER_CONTEXT_ATTRIBUTES,
    build_core_router_context,
    build_deferred_router_context,
    register_core_routers,
    register_deferred_routers,
)
from backend.core.runtime_metrics import (
    new_runtime_metrics_state,
    record_runtime_error,
    record_runtime_request,
)
from backend.core.static_assets import mount_frontend_static
from backend.delivery_templates import (
    install_delivery_template_manifest_payload,
    list_delivery_template_catalog,
    uninstall_delivery_template_manifest_payload,
)
from backend.helpers import (
    build_parallel_agent_streams,
    build_share_url,
    build_single_agent_stream,
    create_session_record,
    decode_share_token,
    delete_kb_directory,
    delete_session_memory_payload,
    encode_share_token,
    kb_health_payload,
    knowledge_bases_payload,
    load_integrator_connectors,
    open_shared_resource_payload,
    pin_session_memory_payload,
    prepare_attachment_promotion,
    prepare_chat_route_runtime,
    reorder_sessions_payload,
    session_attachments_payload,
    session_memory_payload,
    session_memory_updates,
    session_update_requested,
    sse_streaming_response,
    summarize_session_memory_payload,
    update_session_memory_payload,
    workspaces_payload,
)
from backend.helpers.chat_file_helpers import (
    ChatFileConfig,
)
from backend.helpers.chat_file_helpers import (
    prepare_chat_files as _prepare_chat_files_impl,
)
from backend.helpers.chat_input_helpers import (
    SUPPORTED_CHAT_IMAGE_MEDIA_TYPES,
    ChatImageConfig,
)
from backend.helpers.chat_input_helpers import (
    build_user_input as _build_user_input_impl,
)
from backend.helpers.chat_input_helpers import (
    validate_chat_payload as _validate_chat_payload_impl,
)
from backend.helpers.chat_stream_helpers import (
    stream_parallel_sse,
    stream_single_sse,
)
from backend.helpers.deck_report_helpers import (
    apply_deck_update,
    build_create_deck_kwargs,
    build_regenerate_deck_kwargs,
    create_share_link_payload,
    export_deck_payload,
    replace_deck_slide,
    report_download_payload,
    report_markdown_payload,
)
from backend.helpers.document_helpers import (
    build_chat_report_title,
    build_upload_documents_task_record,
    cleanup_temp_paths,
    populate_chat_report_presentation,
    retrieval_test_payload,
    safe_report_filename,
    stage_upload_files,
    upload_documents_response,
)
from backend.helpers.http_runtime_helpers import (
    classify_runtime_error,
)
from backend.helpers.kb_chunk_route_helpers import (
    delete_kb_chunk_payload,
    list_kb_chunks_payload,
    update_kb_chunk_payload,
)
from backend.helpers.kb_helpers import (
    filter_kb_chunks,
)
from backend.helpers.kb_helpers import (
    kb_collect_chunks as _kb_collect_chunks,
)
from backend.helpers.kb_helpers import (
    kb_docstore_dict as _kb_docstore_dict,
)
from backend.helpers.kb_helpers import (
    kb_rebuild_from_documents as _kb_rebuild_from_documents,
)
from backend.helpers.kb_helpers import (
    kb_safe_metadata as _kb_safe_metadata,
)
from backend.helpers.kb_management_helpers import (
    effective_vector_store_path as _effective_vector_store_path_impl,
)
from backend.helpers.security_helpers import (
    sanitize_log_value,
    sanitize_request_path,
)
from backend.helpers.session_helpers import (
    build_answer_group_review_payload as _build_answer_group_review_payload,
)
from backend.helpers.session_helpers import (
    build_session_messages_payload as _build_session_messages_payload,
)
from backend.helpers.session_helpers import (
    collect_session_attachments as _collect_session_attachments,
)
from backend.helpers.session_helpers import (
    find_session_attachment as _find_session_attachment,
)
from backend.helpers.session_helpers import (
    render_shared_deck_html as _render_shared_deck_html,
)
from backend.helpers.session_helpers import (
    render_shared_session_html as _render_shared_session_html,
)
from backend.helpers.session_memory_helpers import (
    build_phase_summary_content,
    build_phase_summary_llm_prompt,
    covered_turns_from_summary,
    latest_auto_summary,
    normalize_llm_text_content,
    summarize_window_meta,
    summary_llm_enabled,
    summary_llm_timeout_seconds,
    summary_turns,
)
from backend.helpers.task_execution_helpers import (
    persist_multi_agent_workflow_task_placeholder,  # noqa: F401 - task runtime context attribute
    persist_multi_agent_workflow_task_result,  # noqa: F401 - task runtime context attribute
    persist_web_research_task_placeholder,
    persist_web_research_task_result,
    run_analyze_knowledge_base_task,
    run_generate_deck_task,
    run_generate_report_task,
    run_multi_agent_workflow_task,
    run_placeholder_task,
    run_promote_attachment_to_kb_task,
    run_upload_documents_task,
    run_web_research_task,
)
from backend.helpers.task_helpers import (
    create_inline_task_record,
    prune_task_records,
    set_inline_task_state,
)
from backend.helpers.task_runtime_helpers import (
    attach_current_kb_status,
    enqueue_task,
    list_tasks_payload,
    task_record_payload,
)
from backend.logging_config import configure_logging
from backend.routes import (
    build_access_router,
    build_agent_catalog_router,
    build_assistant_preset_router,
    build_chat_router,
    build_content_router,
    build_delivery_template_router,
    build_identity_router,
    build_kb_router,
    build_operations_router,
    build_prompt_router,
    build_provider_router,
    build_security_router,
    build_session_router,
)
from backend.routes.operations_routes import run_integrator_scheduler_tick
from backend.schemas.api_models import (
    AgentCatalogResponse,
    ApprovalPolicyRequest,
    ApprovalTaskDecisionRequest,
    AuthTokenCatalogResponse,
    AuthWhoAmIResponse,
    ChatRequest,
    CreateBookmarkRequest,
    CreateDeckRequest,
    CreateMultiAgentWorkflowTaskRequest,
    CreateSessionRequest,
    CreateTaskRequest,
    CreateWorkspaceRequest,
    DeleteResourceGrantRequest,
    DeliveryTemplateCatalogResponse,
    GenerateArtifactRequest,
    GenerateReportRequest,
    IdentityCatalogResponse,
    ImportSessionMessagesRequest,
    MembershipResponse,
    ModelConfig,
    OrganizationResponse,
    PinSessionMemoryRequest,
    ProviderCatalogResponse,
    RegenerateDeckSlideRequest,
    ReorderSessionsRequest,
    ResourceAccessResponse,
    ResourceGrantListResponse,
    ResourceGrantResponse,
    RevokeShareLinkResponse,
    RolePermissionMatrixResponse,
    RuntimeOperationsResponse,
    SecurityAuditActionCatalogResponse,
    SecurityAuditAggregateReportResponse,
    SecurityAuditArchivePolicyResponse,
    SecurityAuditCleanupResponse,
    SecurityAuditEventListResponse,
    SecurityAuditLegalHoldResponse,
    SecurityAuditSiemExportResponse,
    SecurityAuditSummaryResponse,
    SecurityStatusResponse,
    SetMembershipRequest,
    SetMessageFeedbackRequest,
    SetRetrievalFeedbackRequest,
    ShareLinkAuditListResponse,
    ShareLinkResponse,
    SingleChatRequest,
    SsoCallbackResponse,
    SsoConfigResponse,
    SsoLoginResponse,
    SyncExternalIdentityRequest,
    SyncExternalIdentityResponse,
    TruncateSessionMessagesRequest,
    UpdateArtifactRequest,
    UpdateDeckRequest,
    UpdateSessionMemoryRequest,
    UpdateSessionRequest,
    UpdateWorkspaceRequest,
    UpsertOrganizationRequest,
    UpsertResourceGrantRequest,
    UpsertUserRequest,
    UserResponse,
)
from backend.services.artifact_service import (
    artifact_export_formats,
    build_deck_artifact,
    build_report_artifact,
    build_research_archive_artifact,
    sync_deck_artifact,
)
from backend.services.deck_service import (
    build_deck,
    build_export_filename,
    build_report_markdown,
    ensure_deckable_chat,
    export_deck_to_pptx,
    normalize_deck_theme,
    regenerate_deck_slide,
)
from backend.stores import (
    SQLiteAppConfigStore,
    SQLiteSecurityAuditStore,
    SQLiteTaskStore,
    TaskRecord,
    TaskStatus,
)
from backend.stores.factory import (
    create_app_config_store,
    create_artifact_store,
    create_deck_store,
    create_identity_store,
    create_resource_access_store,
    create_security_audit_store,
    create_share_link_store,
    create_sso_session_store,
    create_task_store,
)
from backend.tasks.health import arq_queue_health_payload

BACKEND_DIR = Path(__file__).resolve().parent


class _ApiServerContextSource:
    """Dynamic explicit dependency surface for runtime/router contexts."""

    __slots__ = ("_allowed_attributes",)

    def __init__(self, allowed_attributes: tuple[str, ...]) -> None:
        object.__setattr__(self, "_allowed_attributes", frozenset(allowed_attributes))

    def __getattr__(self, name: str) -> Any:
        if name not in self._allowed_attributes:
            raise AttributeError(f"API server context has no dependency {name!r}")
        try:
            return globals()[name]
        except KeyError as exc:
            raise AttributeError(f"API server context missing dependency {name!r}") from exc

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_allowed_attributes":
            object.__setattr__(self, name, value)
            return
        if name not in self._allowed_attributes:
            raise AttributeError(f"API server context has no dependency {name!r}")
        globals()[name] = value


def _api_server_context_source(
    allowed_attributes: tuple[str, ...],
) -> _ApiServerContextSource:
    return _ApiServerContextSource(allowed_attributes)


# These symbols are consumed through explicit runtime/router context proxies.
# Keeping the reference list here makes that dynamic dependency surface visible
# to static analysis without widening the contexts themselves.
_DYNAMIC_CONTEXT_DEPENDENCIES = (
    AgentCatalogResponse,
    ApprovalPolicyRequest,
    ApprovalTaskDecisionRequest,
    AuthTokenCatalogResponse,
    AuthWhoAmIResponse,
    ChatFileConfig,
    ChatImageConfig,
    ChatRequest,
    CreateBookmarkRequest,
    CreateDeckRequest,
    CreateMultiAgentWorkflowTaskRequest,
    CreateSessionRequest,
    CreateWorkspaceRequest,
    DeleteResourceGrantRequest,
    DeliveryTemplateCatalogResponse,
    GenerateArtifactRequest,
    GenerateReportRequest,
    HTTPException,
    IdentityCatalogResponse,
    ImportSessionMessagesRequest,
    MembershipResponse,
    OrganizationResponse,
    PinSessionMemoryRequest,
    ProviderCatalogResponse,
    RegenerateDeckSlideRequest,
    ReorderSessionsRequest,
    ResourceAccessResponse,
    ResourceGrantListResponse,
    ResourceGrantResponse,
    RevokeShareLinkResponse,
    RolePermissionMatrixResponse,
    RuntimeOperationsResponse,
    SecurityAuditActionCatalogResponse,
    SecurityAuditAggregateReportResponse,
    SecurityAuditArchivePolicyResponse,
    SecurityAuditCleanupResponse,
    SecurityAuditEventListResponse,
    SecurityAuditLegalHoldResponse,
    SecurityAuditSiemExportResponse,
    SecurityAuditSummaryResponse,
    SecurityStatusResponse,
    SetMembershipRequest,
    SetMessageFeedbackRequest,
    SetRetrievalFeedbackRequest,
    ShareLinkAuditListResponse,
    ShareLinkResponse,
    SingleChatRequest,
    SQLiteAppConfigStore,
    SsoCallbackResponse,
    SsoConfigResponse,
    SsoLoginResponse,
    SUPPORTED_CHAT_IMAGE_MEDIA_TYPES,
    SyncExternalIdentityRequest,
    SyncExternalIdentityResponse,
    TruncateSessionMessagesRequest,
    UpdateArtifactRequest,
    UpdateDeckRequest,
    UpdateSessionMemoryRequest,
    UpdateSessionRequest,
    UpdateWorkspaceRequest,
    UpsertOrganizationRequest,
    UpsertResourceGrantRequest,
    UpsertUserRequest,
    UserResponse,
    _build_answer_group_review_payload,
    _build_session_messages_payload,
    _build_user_input_impl,
    _collect_session_attachments,
    _find_session_attachment,
    _kb_collect_chunks,
    _kb_docstore_dict,
    _kb_rebuild_from_documents,
    _kb_safe_metadata,
    _prepare_chat_files_impl,
    _render_shared_deck_html,
    _render_shared_session_html,
    _validate_chat_payload_impl,
    apply_deck_update,
    arq_queue_health_payload,
    artifact_export_formats,
    attach_current_kb_status,
    build_access_router,
    build_agent_catalog_router,
    build_assistant_preset_router,
    build_chat_report_title,
    build_chat_router,
    build_content_router,
    build_create_deck_kwargs,
    build_deck,
    build_deck_artifact,
    build_delivery_template_router,
    build_export_filename,
    build_phase_summary_content,
    build_phase_summary_llm_prompt,
    build_identity_router,
    build_kb_router,
    build_operations_router,
    build_parallel_agent_streams,
    build_prompt_router,
    build_provider_router,
    build_regenerate_deck_kwargs,
    build_report_artifact,
    build_report_markdown,
    build_research_archive_artifact,
    build_security_router,
    build_session_router,
    build_share_url,
    build_single_agent_stream,
    build_upload_documents_task_record,
    cleanup_temp_paths,
    create_inline_task_record,
    create_session_record,
    create_share_link_payload,
    create_task_store,
    decode_share_token,
    default_mcp_server_names,
    delete_kb_chunk_payload,
    delete_kb_directory,
    delete_session_memory_payload,
    encode_share_token,
    ensure_deckable_chat,
    export_deck_payload,
    export_deck_to_pptx,
    filter_kb_chunks,
    install_agent_plugin_manifest_payload,
    install_delivery_template_manifest_payload,
    kb_health_payload,
    knowledge_bases_payload,
    list_agent_catalog,
    list_delivery_template_catalog,
    list_kb_chunks_payload,
    list_llm_provider_catalog,
    list_mcp_server_catalog,
    list_tasks_payload,
    load_integrator_connectors,
    covered_turns_from_summary,
    latest_auto_summary,
    normalize_deck_theme,
    normalize_llm_text_content,
    open_shared_resource_payload,
    persist_multi_agent_workflow_task_placeholder,
    persist_web_research_task_placeholder,
    persist_web_research_task_result,
    pin_session_memory_payload,
    populate_chat_report_presentation,
    prepare_attachment_promotion,
    prepare_chat_route_runtime,
    prune_task_records,
    re,
    regenerate_deck_slide,
    reorder_sessions_payload,
    replace_deck_slide,
    report_download_payload,
    report_markdown_payload,
    retrieval_test_payload,
    run_analyze_knowledge_base_task,
    run_generate_deck_task,
    run_generate_report_task,
    run_multi_agent_workflow_task,
    run_placeholder_task,
    run_promote_attachment_to_kb_task,
    run_upload_documents_task,
    run_web_research_task,
    safe_report_filename,
    session_attachments_payload,
    session_memory_payload,
    session_memory_updates,
    session_update_requested,
    set_inline_task_state,
    sse_streaming_response,
    stage_upload_files,
    stream_parallel_sse,
    stream_single_sse,
    summarize_window_meta,
    summarize_session_memory_payload,
    summary_llm_enabled,
    summary_llm_timeout_seconds,
    summary_turns,
    sync_deck_artifact,
    task_record_payload,
    update_kb_chunk_payload,
    update_session_memory_payload,
    uninstall_agent_plugin_manifest_payload,
    uninstall_delivery_template_manifest_payload,
    upload_documents_response,
    workspaces_payload,
)


load_dotenv()

_log_format = configure_logging()
logger = logging.getLogger(__name__)
logger.info("日志格式: %s", _log_format)

_app_config_store = create_app_config_store()
MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY = (
    mcp_runtime_helpers.MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY
)


def get_mcp_runtime_health_history(limit: Any = 10) -> dict[str, Any]:
    return mcp_runtime_helpers.runtime_health_history_payload(
        _app_config_store,
        limit=limit,
        fallback_reader=_get_mcp_runtime_health_history,
        logger=logger,
    )


async def list_mcp_server_runtime_health(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault(
        "history_recorder",
        lambda snapshot, history_limit: (
            mcp_runtime_helpers.persist_runtime_health_history_item(
                _app_config_store,
                snapshot,
                history_limit,
            )
        ),
    )
    kwargs.setdefault(
        "history_reader",
        lambda limit=None: mcp_runtime_helpers.stored_runtime_health_history(
            _app_config_store,
            limit,
        ),
    )
    return await _list_mcp_server_runtime_health(**kwargs)


def current_mcp_approved_connectors_payload() -> dict[str, Any]:
    return mcp_runtime_helpers.approvals_payload_with_persistence(
        _app_config_store,
        runtime_payload=_current_mcp_approved_connectors_payload,
        set_runtime_connectors=_set_runtime_mcp_approved_connectors,
    )


def set_runtime_mcp_approved_connectors(raw_value: Any) -> list[str]:
    return mcp_runtime_helpers.persist_mcp_approved_connectors(
        _app_config_store,
        raw_value,
        set_runtime_connectors=_set_runtime_mcp_approved_connectors,
    )


def clear_runtime_mcp_approved_connectors() -> list[str]:
    return mcp_runtime_helpers.persist_mcp_approved_connectors(
        _app_config_store,
        [],
        set_runtime_connectors=_set_runtime_mcp_approved_connectors,
    )


def approve_runtime_mcp_connector(connector_name: Any) -> dict[str, Any]:
    return mcp_runtime_helpers.approve_persisted_runtime_mcp_connector(
        _app_config_store,
        connector_name,
        runtime_payload=_current_mcp_approved_connectors_payload,
        set_runtime_connectors=_set_runtime_mcp_approved_connectors,
    )


def revoke_runtime_mcp_connector(connector_name: Any) -> dict[str, Any]:
    return mcp_runtime_helpers.revoke_persisted_runtime_mcp_connector(
        _app_config_store,
        connector_name,
        runtime_payload=_current_mcp_approved_connectors_payload,
        set_runtime_connectors=_set_runtime_mcp_approved_connectors,
    )


try:
    mcp_runtime_helpers.hydrate_runtime_mcp_approved_connectors(
        _app_config_store,
        set_runtime_connectors=_set_runtime_mcp_approved_connectors,
    )
except Exception:
    logger.exception("Failed to hydrate persisted MCP connector approvals")


_sso_runtime_context_cache = None


def _sso_runtime_context():
    global _sso_runtime_context_cache
    if _sso_runtime_context_cache is None:
        _sso_runtime_context_cache = sso_runtime.build_sso_runtime_context(
            _api_server_context_source(sso_runtime.SSO_RUNTIME_CONTEXT_ATTRIBUTES)
        )
    return _sso_runtime_context_cache


def _stored_sso_config_value(field: str) -> str | None:
    return sso_runtime.stored_sso_config_value(_sso_runtime_context(), field)


def _effective_sso_config_value(field: str) -> str:
    return sso_runtime.effective_sso_config_value(_sso_runtime_context(), field)


def _effective_sso_session_ttl_seconds() -> int:
    return sso_runtime.effective_sso_session_ttl_seconds(_sso_runtime_context())


sync_runtime_secret_from_store(
    _app_config_store,
    logger,
    "TAVILY_API_KEY",
    "tavily_api_key",
)


PROJECT_ROOT = BACKEND_DIR.parent
UPLOAD_CHUNK_SIZE = 1024 * 1024
TASK_HISTORY_LIMIT = 200
TASK_HISTORY_TTL_SECONDS = int(os.getenv("TASK_HISTORY_TTL_SECONDS", str(6 * 60 * 60)))
TASK_BACKEND = os.getenv("TASK_BACKEND", "memory").strip().lower() or "memory"
enqueue_external_task = None
cancel_external_task = None
KB_METADATA_TTL_SECONDS = 30
CHAT_FILE_CONTEXT_START_MARKER = "[[CHAT_FILE_CONTEXT_START]]"
CHAT_FILE_CONTEXT_END_MARKER = "[[CHAT_FILE_CONTEXT_END]]"
CHAT_FILE_MAX_COUNT = int(os.getenv("CHAT_FILE_MAX_COUNT", "6"))
CHAT_FILE_MAX_BYTES = int(os.getenv("CHAT_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
CHAT_FILE_MAX_CHARS_PER_FILE = int(os.getenv("CHAT_FILE_MAX_CHARS_PER_FILE", "8000"))
CHAT_FILE_MAX_TOTAL_CHARS = int(os.getenv("CHAT_FILE_MAX_TOTAL_CHARS", "24000"))
CHAT_ATTACHMENT_PREVIEW_CHARS = int(os.getenv("CHAT_ATTACHMENT_PREVIEW_CHARS", "4000"))
CHAT_IMAGE_MAX_COUNT = int(os.getenv("CHAT_IMAGE_MAX_COUNT", "4"))
CHAT_IMAGE_MAX_BYTES = int(os.getenv("CHAT_IMAGE_MAX_BYTES", str(10 * 1024 * 1024)))
CHAT_IMAGE_MAX_TOTAL_BYTES = int(
    os.getenv("CHAT_IMAGE_MAX_TOTAL_BYTES", str(20 * 1024 * 1024))
)
SHARE_LINK_SECRET = os.getenv("SHARE_LINK_SECRET", "local-share-secret")
SHARE_LINK_TTL_SECONDS = int(os.getenv("SHARE_LINK_TTL_SECONDS", str(7 * 24 * 60 * 60)))
DEFAULT_SHARE_LINK_SECRET = "local-share-secret"
MIN_SHARE_LINK_SECRET_LENGTH = 16
MIN_AUTH_TOKEN_RECOMMENDED_LENGTH = 16
AUTH_ROLE_RANKS = {"viewer": 1, "editor": 2, "admin": 3}
DEFAULT_AUTH_ROLE = "viewer"
DEFAULT_AUTH_USER_IDS = {
    "viewer": "viewer",
    "editor": "editor",
    "admin": "admin",
}
SSO_PROVIDER = os.getenv("SSO_PROVIDER", "none")
OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", "")
OIDC_AUTHORIZATION_ENDPOINT = os.getenv("OIDC_AUTHORIZATION_ENDPOINT", "")
OIDC_TOKEN_ENDPOINT = os.getenv("OIDC_TOKEN_ENDPOINT", "")
OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL", "")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_ALLOWED_DOMAINS = os.getenv("OIDC_ALLOWED_DOMAINS", "")
OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid email profile")
SSO_LOGIN_STATE_TTL_SECONDS = 10 * 60
SSO_SESSION_TTL_SECONDS = int(os.getenv("SSO_SESSION_TTL_SECONDS", str(8 * 60 * 60)))
SSO_DEFAULT_ROLE = os.getenv("SSO_DEFAULT_ROLE", DEFAULT_AUTH_ROLE)
_SSO_CONFIG_FIELDS = {
    "provider": ("SSO_PROVIDER", "SSO_PROVIDER", "sso.provider", "none"),
    "issuer_url": ("OIDC_ISSUER_URL", "OIDC_ISSUER_URL", "sso.oidc_issuer_url", ""),
    "authorization_endpoint": (
        "OIDC_AUTHORIZATION_ENDPOINT",
        "OIDC_AUTHORIZATION_ENDPOINT",
        "sso.oidc_authorization_endpoint",
        "",
    ),
    "token_endpoint": (
        "OIDC_TOKEN_ENDPOINT",
        "OIDC_TOKEN_ENDPOINT",
        "sso.oidc_token_endpoint",
        "",
    ),
    "jwks_url": ("OIDC_JWKS_URL", "OIDC_JWKS_URL", "sso.oidc_jwks_url", ""),
    "client_id": ("OIDC_CLIENT_ID", "OIDC_CLIENT_ID", "sso.oidc_client_id", ""),
    "client_secret": (
        "OIDC_CLIENT_SECRET",
        "OIDC_CLIENT_SECRET",
        "sso.oidc_client_secret",
        "",
    ),
    "allowed_domains": (
        "OIDC_ALLOWED_DOMAINS",
        "OIDC_ALLOWED_DOMAINS",
        "sso.oidc_allowed_domains",
        "",
    ),
    "scopes": ("OIDC_SCOPES", "OIDC_SCOPES", "sso.oidc_scopes", "openid email profile"),
    "default_role": ("SSO_DEFAULT_ROLE", "SSO_DEFAULT_ROLE", "sso.default_role", DEFAULT_AUTH_ROLE),
    "session_ttl_seconds": (
        "SSO_SESSION_TTL_SECONDS",
        "SSO_SESSION_TTL_SECONDS",
        "sso.session_ttl_seconds",
        str(8 * 60 * 60),
    ),
}
_INITIAL_SSO_CONFIG_VALUES = {
    attr_name: str(globals().get(attr_name, default) or "").strip()
    for attr_name, _, _, default in _SSO_CONFIG_FIELDS.values()
}
SECURITY_AUDIT_MEMORY_WINDOW_LIMIT = 200
SECURITY_AUDIT_HISTORY_LIMIT, SECURITY_AUDIT_HISTORY_LIMIT_SOURCE = env_runtime.env_int_setting(
    "SECURITY_AUDIT_HISTORY_LIMIT",
    2000,
    minimum=1,
    runtime_logger=logger,
)
(
    REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS,
    REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE,
) = env_runtime.env_int_setting(
    "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS",
    60,
    minimum=1,
    runtime_logger=logger,
)
(
    REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS,
    REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS_SOURCE,
) = env_runtime.env_int_setting(
    "REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS",
    30,
    minimum=1,
    runtime_logger=logger,
)
REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED = str(
    os.getenv("REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED", "true") or "true"
).strip().lower() in {"1", "true", "yes", "on"}
RUNTIME_RECENT_ERROR_LIMIT = 20
DEEP_RESEARCH_MAX_CONCURRENCY, DEEP_RESEARCH_MAX_CONCURRENCY_SOURCE = env_runtime.env_int_setting(
    "DEEP_RESEARCH_MAX_CONCURRENCY",
    2,
    minimum=1,
    runtime_logger=logger,
)
SESSION_MEMORY_AUTO_SUMMARY_MIN_TURNS = int(
    os.getenv("SESSION_MEMORY_AUTO_SUMMARY_MIN_TURNS", "12")
)
SESSION_MEMORY_AUTO_SUMMARY_MIN_NEW_TURNS = int(
    os.getenv("SESSION_MEMORY_AUTO_SUMMARY_MIN_NEW_TURNS", "6")
)
SESSION_MEMORY_AUTO_SUMMARY_WINDOW_SIZE = int(
    os.getenv("SESSION_MEMORY_AUTO_SUMMARY_WINDOW_SIZE", "14")
)
SESSION_MEMORY_AUTO_SUMMARY_MAX_CONTENT_CHARS = int(
    os.getenv("SESSION_MEMORY_AUTO_SUMMARY_MAX_CONTENT_CHARS", "900")
)
SUPPORTED_CHAT_FILE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".xls",
    ".xlsx",
}
DOCUMENT_UPLOAD_MAX_COUNT = int(os.getenv("DOCUMENT_UPLOAD_MAX_COUNT", "20"))
DOCUMENT_UPLOAD_MAX_FILE_BYTES = int(
    os.getenv("DOCUMENT_UPLOAD_MAX_FILE_BYTES", str(25 * 1024 * 1024))
)
DOCUMENT_UPLOAD_MAX_TOTAL_BYTES = int(
    os.getenv("DOCUMENT_UPLOAD_MAX_TOTAL_BYTES", str(100 * 1024 * 1024))
)
DOCUMENT_UPLOAD_STAGING_DIR = str(os.getenv("DOCUMENT_UPLOAD_STAGING_DIR", "")).strip() or None


@dataclass
class KBMetadataCacheEntry:
    expires_at: float
    value: dict[str, Any]


_security_runtime_context_cache = None


def _security_runtime_context():
    global _security_runtime_context_cache
    if _security_runtime_context_cache is None:
        _security_runtime_context_cache = (
            security_runtime.build_security_runtime_context(
                _api_server_context_source(
                    security_runtime.SECURITY_RUNTIME_CONTEXT_ATTRIBUTES
                )
            )
        )
    return _security_runtime_context_cache


def _request_is_local(request: Request) -> bool:
    return security_runtime._request_is_local(_security_runtime_context(), request)


def _remote_management_rate_limit_status() -> dict[str, Any]:
    return security_runtime._remote_management_rate_limit_status(
        _security_runtime_context()
    )


def _security_status_payload() -> dict[str, Any]:
    return security_runtime._security_status_payload(_security_runtime_context())


def _set_sso_config_field(field: str, value: str) -> None:
    sso_runtime.set_sso_config_field(_sso_runtime_context(), field, value)


def _sso_callback_url(request: Request) -> str:
    return sso_runtime.sso_callback_url(request)


def _prune_sso_login_states(now: float | None = None) -> None:
    sso_runtime.prune_sso_login_states(_sso_runtime_context(), now=now)


def _prune_sso_sessions(now: float | None = None) -> None:
    sso_runtime.prune_sso_sessions(_sso_runtime_context(), now=now)


def _issue_sso_session_token(*, user_id: str, role: str) -> dict[str, Any]:
    return sso_runtime.issue_sso_session_token(
        _sso_runtime_context(),
        user_id=user_id,
        role=role,
    )


def _resolve_sso_session_token(token: str) -> dict[str, str] | None:
    return sso_runtime.resolve_sso_session_token(_sso_runtime_context(), token)


def _sso_login_payload(request: Request, response_mode: str = "") -> dict[str, Any]:
    return sso_runtime.sso_login_payload(
        _sso_runtime_context(),
        request,
        response_mode=response_mode,
    )


async def _exchange_oidc_code(
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    return await sso_runtime.exchange_oidc_code(
        _sso_runtime_context(),
        code=code,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
    )


def _verify_oidc_id_token(id_token: str, *, nonce: str) -> dict[str, Any]:
    return sso_runtime.verify_oidc_id_token(
        _sso_runtime_context(),
        id_token,
        nonce=nonce,
    )


async def _sso_callback_payload(
    request: Request,
    *,
    code: str,
    state: str,
) -> dict[str, Any]:
    return await sso_runtime.sso_callback_payload(
        _sso_runtime_context(),
        request,
        code=code,
        state=state,
    )


def _get_security_audit_store() -> SQLiteSecurityAuditStore:
    global _security_audit_store
    if _security_audit_store is None:
        with _security_audit_store_init_lock:
            if _security_audit_store is None:
                _security_audit_store = create_security_audit_store(
                    history_limit=SECURITY_AUDIT_HISTORY_LIMIT
                )
    return _security_audit_store


def _persist_security_audit_event(event: dict[str, Any]) -> None:
    try:
        _get_security_audit_store().append(event)
    except Exception:
        logger.exception(
            "Failed to persist security audit event action=%s request_id=%s",
            event.get("action"),
            event.get("request_id"),
        )


def _get_sso_session_store():
    global _sso_session_store
    if _sso_session_store is None:
        with _sso_session_store_init_lock:
            if _sso_session_store is None:
                _sso_session_store = create_sso_session_store()
    return _sso_session_store


def _active_vector_store_id() -> str | None:
    _, vector_store_path, _ = prompt_runtime.resolve_active_prompt_runtime(True)
    return vector_store_path


def _effective_vector_store_path(candidate: str | None = None) -> str:
    raw = str(candidate or "").strip()
    return _effective_vector_store_path_impl(
        candidate,
        project_root=PROJECT_ROOT,
        active_vector_store_id=None if raw else _active_vector_store_id(),
        env_vector_store_path=os.getenv("VECTOR_STORE_PATH", "./vector_store"),
    )


ALLOW_REMOTE_CLIENTS = env_runtime.env_flag("ALLOW_REMOTE_CLIENTS", False)
_cors_origins, _cors_allow_credentials = env_runtime.cors_settings()
_REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES = (
    "/api/security/",
    "/api/auth/",
    "/api/access/",
    "/api/identity",
    "/api/operations/runtime",
    "/api/config",
    "/api/prompts",
    "/api/share-links",
    "/api/agents/",
    "/api/documents/upload",
    "/api/documents/stats",
    "/api/knowledge-base",
    "/api/knowledge-bases",
)

app = FastAPI(title="InsightDesk API", version="2.0.0")
_deck_store = create_deck_store()
_artifact_store = create_artifact_store()
_share_link_store = create_share_link_store()
_identity_store = create_identity_store()
_resource_access_store = create_resource_access_store()
_runtime_started_at = time.time()
_security_audit_events_lock = threading.Lock()
_runtime_metrics_lock = threading.Lock()
_remote_management_rate_limit_lock = threading.Lock()
_security_audit_events: list[dict[str, Any]] = []
_security_audit_store: SQLiteSecurityAuditStore | None = None
_security_audit_store_init_lock = threading.Lock()
_sso_session_store = None
_sso_session_store_init_lock = threading.Lock()
_remote_management_rate_limits: dict[str, dict[str, float]] = {}
_sso_login_states_lock = threading.Lock()
_sso_login_states: dict[str, dict[str, Any]] = {}
_sso_sessions_lock = threading.Lock()
_sso_sessions: dict[str, dict[str, Any]] = {}

_runtime_metrics = new_runtime_metrics_state()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

if rate_limit.general_rate_limit_enabled():
    _general_rpm, _general_burst = rate_limit.general_rate_limit_limits()
    app.add_middleware(
        BaseHTTPMiddleware,
        dispatch=rate_limit.rate_limit_middleware_factory(
            rate_limit.RateLimiter(
                requests_per_minute=_general_rpm,
                burst=_general_burst,
            )
        ),
    )


@app.middleware("http")
async def restrict_remote_clients(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    try:
        if ALLOW_REMOTE_CLIENTS:
            rate_limit_payload = security_runtime._consume_remote_management_rate_limit(
                _security_runtime_context(),
                request,
            )
            request.state.remote_management_rate_limit = rate_limit_payload
            if rate_limit_payload and not rate_limit_payload["allowed"]:
                security_runtime._audit_security_event(
                    _security_runtime_context(),
                    "remote_management_rate_limit",
                    request,
                    result="blocked",
                    details=(
                        f"path={rate_limit_payload['path']} "
                        f"principal={rate_limit_payload['principal']} "
                        f"limit={rate_limit_payload['limit']} "
                        f"window_seconds={rate_limit_payload['window_seconds']}"
                    ),
                )
                response = JSONResponse(
                    status_code=429,
                    content={
                        "code": "RATE_LIMIT",
                        "message": "Too many remote management requests.",
                        "suggestion": "Please wait briefly before retrying this management operation.",
                    },
                )
            else:
                response = await call_next(request)
        else:
            if request_runtime.request_is_local_origin(request):
                response = await call_next(request)
            else:
                logger.warning(
                    "Blocked non-local request request_id=%s host=%s path=%s",
                    request_id,
                    request_runtime.request_client_ip(request),
                    sanitize_request_path(request.url.path),
                )
                response = JSONResponse(
                    status_code=403,
                    content={
                        "code": "LOCAL_ONLY",
                        "message": "Local access only.",
                        "suggestion": "Use localhost/127.0.0.1 or set ALLOW_REMOTE_CLIENTS=true before exposing the server.",
                    },
                )
    except Exception as exc:
        response = await global_exception_handler(request, exc)

    process_time_ms = (time.perf_counter() - started_at) * 1000.0
    record_runtime_request(
        _runtime_metrics,
        _runtime_metrics_lock,
        status_code=int(response.status_code),
        timestamp=time.time(),
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    rate_limit_payload = getattr(request.state, "remote_management_rate_limit", None)
    if isinstance(rate_limit_payload, dict):
        response.headers["X-RateLimit-Limit"] = str(rate_limit_payload["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_payload["remaining"])
        response.headers["X-RateLimit-Reset"] = str(
            rate_limit_payload["reset_after_seconds"]
        )
        response.headers["X-RateLimit-Scope"] = "remote-management"
        if (
            int(response.status_code) == 429
            and int(rate_limit_payload["retry_after"]) > 0
        ):
            response.headers["Retry-After"] = str(rate_limit_payload["retry_after"])
    logger.info(
        "request_id=%s method=%s path=%s status=%s latency_ms=%.2f",
        request_id,
        request.method,
        sanitize_request_path(request.url.path),
        response.status_code,
        process_time_ms,
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err = classify_runtime_error(exc)
    request_id = getattr(request.state, "request_id", "")
    logger.exception(
        "Unhandled exception request_id=%s on %s", request_id, request.url.path
    )
    record_runtime_error(
        _runtime_metrics,
        _runtime_metrics_lock,
        request=request,
        status_code=500,
        error_code=str(err["code"] or "").strip(),
        message=str(exc or err["message"]).strip() or str(err["message"]).strip(),
        sanitize_request_path=sanitize_request_path,
        sanitize_log_value=sanitize_log_value,
        recent_error_limit=RUNTIME_RECENT_ERROR_LIMIT,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": err["code"],
            "message": err["message"],
            "suggestion": err["suggestion"],
            "request_id": request_id,
        },
    )


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# Pydantic 请求/响应模型
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 异步任务状态机
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


_task_runtime_context_cache = None


def _task_runtime_context():
    global _task_runtime_context_cache
    if _task_runtime_context_cache is None:
        _task_runtime_context_cache = task_runtime.build_task_runtime_context(
            _api_server_context_source(task_runtime.TASK_RUNTIME_CONTEXT_ATTRIBUTES)
        )
    return _task_runtime_context_cache


def _update_task_progress(record: TaskRecord, progress: int) -> None:
    return task_runtime._update_task_progress(_task_runtime_context(), record, progress)


async def _drop_suppressed_task(record: TaskRecord) -> bool:
    return await task_runtime._drop_suppressed_task(_task_runtime_context(), record)


async def _create_inline_task_record(
    task_type: str,
    params: dict[str, Any],
    *,
    session_id: str | None = None,
    progress: int = 10,
) -> TaskRecord:
    return await task_runtime._create_inline_task_record(
        _task_runtime_context(),
        task_type,
        params,
        session_id=session_id,
        progress=progress,
    )


async def _set_inline_task_state(
    record: TaskRecord,
    *,
    status: TaskStatus,
    progress: int | None = None,
    result: str | None = None,
    error: str | None = None,
) -> TaskRecord:
    return await task_runtime._set_inline_task_state(
        _task_runtime_context(),
        record,
        status=status,
        progress=progress,
        result=result,
        error=error,
    )


def _is_deep_research_task(record: TaskRecord) -> bool:
    return task_runtime._is_deep_research_task(_task_runtime_context(), record)


def _get_deep_research_semaphore() -> asyncio.Semaphore:
    return task_runtime._get_deep_research_semaphore(_task_runtime_context())


def _get_task_store() -> SQLiteTaskStore:
    return task_runtime._get_task_store(_task_runtime_context())


def _persist_task_record(record: TaskRecord) -> None:
    return task_runtime._persist_task_record(_task_runtime_context(), record)


def _prune_persisted_tasks() -> None:
    return task_runtime._prune_persisted_tasks(_task_runtime_context())


def _prune_task_records_locked(now: float | None = None) -> None:
    return task_runtime._prune_task_records_locked(_task_runtime_context(), now)


async def _run_task(record: TaskRecord) -> None:
    return await task_runtime._run_task(_task_runtime_context(), record)


async def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    return await task_runtime.create_task(_task_runtime_context(), request)


async def get_task(task_id: str) -> dict[str, Any]:
    return await task_runtime.get_task(_task_runtime_context(), task_id)


async def list_tasks(limit: int = 20) -> dict[str, Any]:
    return await task_runtime.list_tasks(_task_runtime_context(), limit)


_tasks: dict[str, TaskRecord] = {}
_tasks_lock = asyncio.Lock()
_integrator_scheduler_tick_lock = asyncio.Lock()
_integrator_scheduler_task: asyncio.Task | None = None
_suppressed_task_ids: set[str] = set()
_deep_research_semaphore_lock = threading.Lock()
_deep_research_semaphores: dict[int, asyncio.Semaphore] = {}
_task_store: SQLiteTaskStore | None = None
_task_store_init_lock = threading.Lock()


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 内部工具函数
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

# 缓存已构建的 agent 实例，key = (provider, model, base_url, api_key, temperature, agent_mode)
_agent_cache: dict[str, Any] = {}
_agent_cache_lock = asyncio.Lock()


_agent_stream_runtime_context_cache: Any | None = None


def _agent_stream_runtime_context() -> Any:
    global _agent_stream_runtime_context_cache
    if _agent_stream_runtime_context_cache is None:
        _agent_stream_runtime_context_cache = (
            agent_stream_runtime.build_agent_stream_runtime_context(
                _api_server_context_source(
                    agent_stream_runtime.AGENT_STREAM_RUNTIME_CONTEXT_ATTRIBUTES
                )
            )
        )
    return _agent_stream_runtime_context_cache


async def _clear_agent_cache() -> None:
    return await agent_stream_runtime.clear_agent_cache(_agent_stream_runtime_context())


async def _get_or_build_agent(*args: Any, **kwargs: Any) -> Any:
    return await agent_stream_runtime.get_or_build_agent(
        _agent_stream_runtime_context(), *args, **kwargs
    )


def _invoke_agent_stream(*args: Any, **kwargs: Any) -> Any:
    # the moved implementation is an async generator function; returning the
    # generator (not awaiting) preserves `async for` semantics for callers
    return agent_stream_runtime.invoke_agent_stream(
        _agent_stream_runtime_context(), *args, **kwargs
    )


_session_summary_runtime_context_cache = None


def _session_summary_runtime_context():
    global _session_summary_runtime_context_cache
    if _session_summary_runtime_context_cache is None:
        _session_summary_runtime_context_cache = (
            session_summary_runtime.build_session_summary_runtime_context(
                _api_server_context_source(
                    session_summary_runtime.SESSION_SUMMARY_RUNTIME_CONTEXT_ATTRIBUTES
                )
            )
        )
    return _session_summary_runtime_context_cache


def _resolve_summary_model_config(
    session_id: str, preferred_model_config: dict[str, Any] | None = None
) -> ModelConfig | None:
    return session_summary_runtime._resolve_summary_model_config(
        _session_summary_runtime_context(), session_id, preferred_model_config
    )






async def _run_integrator_scheduler_tick_once(
    *,
    now: float | None = None,
) -> dict[str, Any]:
    return await run_integrator_scheduler_tick(
        _app_config_store,
        tick_lock=_integrator_scheduler_tick_lock,
        now=now,
        tasks=lambda: _tasks,
        tasks_lock=_tasks_lock,
        prune_task_records_locked=_prune_task_records_locked,
        persist_task_record=_persist_task_record,
        prune_persisted_tasks=_prune_persisted_tasks,
        run_task=_run_task,
        enqueue_task=enqueue_task,
        spawn_background_task=lambda coro: asyncio.ensure_future(coro),
        logger=logger,
        task_backend=lambda: TASK_BACKEND,
        enqueue_external_task=enqueue_external_task,
    )


async def _integrator_scheduler_loop(interval_seconds: int) -> None:
    logger.info(
        "Integrator scheduler worker started: interval_seconds=%s",
        interval_seconds,
    )
    try:
        while True:
            try:
                result = await _run_integrator_scheduler_tick_once()
                if result.get("due_count") or result.get("status") == "skipped":
                    logger.info(
                        "Integrator scheduler tick: status=%s checked=%s due=%s executed=%s",
                        result.get("status", "ok"),
                        result.get("checked", 0),
                        result.get("due_count", 0),
                        result.get("executed", False),
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Integrator scheduler tick failed")
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Integrator scheduler worker stopped")
        raise


def _start_integrator_scheduler_worker() -> bool:
    global _integrator_scheduler_task

    config = env_runtime.integrator_scheduler_config(runtime_logger=logger)
    if not config["enabled"]:
        logger.info(
            "Integrator scheduler worker disabled: enabled_source=%s interval_seconds=%s",
            config["enabled_source"],
            config["interval_seconds"],
        )
        return False

    if _integrator_scheduler_task is not None and not _integrator_scheduler_task.done():
        logger.info("Integrator scheduler worker already running")
        return True

    _integrator_scheduler_task = asyncio.create_task(
        _integrator_scheduler_loop(int(config["interval_seconds"])),
        name="integrator-scheduler-worker",
    )
    return True


async def _stop_integrator_scheduler_worker() -> bool:
    global _integrator_scheduler_task

    task = _integrator_scheduler_task
    if task is None:
        return False

    _integrator_scheduler_task = None
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return True


async def _startup_integrator_scheduler_worker() -> None:
    app.state.integrator_scheduler_worker_started = _start_integrator_scheduler_worker()


async def _shutdown_integrator_scheduler_worker() -> None:
    app.state.integrator_scheduler_worker_stopped = (
        await _stop_integrator_scheduler_worker()
    )


register_app_lifecycle_handler(app, "startup", _startup_integrator_scheduler_worker)
register_app_lifecycle_handler(app, "shutdown", _shutdown_integrator_scheduler_worker)


_core_router_context = build_core_router_context(
    _api_server_context_source(_CORE_ROUTER_CONTEXT_ATTRIBUTES)
)
_deferred_router_context = build_deferred_router_context(
    _api_server_context_source(_DEFERRED_ROUTER_CONTEXT_ATTRIBUTES)
)
register_core_routers(_core_router_context)
register_deferred_routers(_deferred_router_context)
mount_frontend_static(app, backend_file=__file__)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        reload=True,
    )
