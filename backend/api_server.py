"""
FastAPI 后端 API 服务
提供 REST + SSE 端点，包装现有 agent_core / chat_store / doc_pipeline 模块
"""

import asyncio
import base64
from dataclasses import dataclass
import hashlib
import httpx
import importlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time
from urllib.parse import quote
import uuid
from typing import Any, AsyncGenerator, Optional

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _alias_backend_module(short_name: str) -> None:
    if short_name in sys.modules:
        return
    sys.modules[short_name] = importlib.import_module(f"backend.{short_name}")


for _module_alias in (
    "artifact_service",
    "agent_core",
    "agent_mcp_helpers",
    "api_agent_stream_helpers",
    "api_attachment_route_helpers",
    "api_chat_file_helpers",
    "api_chat_input_helpers",
    "api_chat_route_helpers",
    "api_chat_stream_helpers",
    "api_config_store",
    "api_deck_report_helpers",
    "api_document_helpers",
    "api_kb_chunk_route_helpers",
    "api_kb_delete_helpers",
    "api_kb_helpers",
    "api_kb_management_helpers",
    "api_session_helpers",
    "api_session_memory_helpers",
    "api_session_memory_route_helpers",
    "api_share_helpers",
    "api_shared_resource_helpers",
    "api_task_execution_helpers",
    "api_task_helpers",
    "api_task_runtime_helpers",
    "api_task_store",
    "api_workspace_session_helpers",
    "chat_store",
    "deck_service",
    "doc_pipeline",
):
    _alias_backend_module(_module_alias)

from backend.core import session_summary_runtime
from backend.core import task_runtime
from backend.core import security_runtime
from backend.core.config_runtime import (
    cloud_model_api_key_config_key,
    delete_cloud_model_api_key,
    normalize_cloud_model_api_key_ref,
    resolve_model_api_key,
    stored_config_value,
    sync_runtime_secret_from_store,
    upsert_cloud_model_api_key,
    validate_tavily_api_key,
)
from backend.core.static_assets import mount_frontend_static
from backend.core.router_registration import (
    register_core_routers,
    register_deferred_routers,
)
from backend.core.runtime_metrics import (
    new_runtime_metrics_state,
    record_runtime_error,
    record_runtime_request,
    runtime_llm_metrics_payload,
    runtime_operations_summary_payload,
    runtime_request_metrics_payload,
    runtime_status_class,
)
from backend.helpers.security_helpers import (
    auth_capabilities_for_role as _build_auth_capabilities_for_role,
    build_auth_token_catalog_payload as _build_auth_token_catalog_payload,
    build_auth_whoami_payload,
    build_role_permission_matrix_payload as _build_role_permission_matrix_payload,
    build_security_audit_action_catalog_payload as _build_security_audit_action_catalog_payload,
    build_security_audit_summary_payload as _build_security_audit_summary_payload,
    build_security_status_payload as _build_security_status_payload,
    build_sso_config_payload as _build_sso_config_payload,
    build_sso_login_payload as _build_sso_login_payload,
    security_audit_category_for_action as _security_audit_category_for_action,
)
from backend.helpers.identity_helpers import sync_external_identity as _sync_external_identity
from backend.helpers import delete_kb_directory
from backend.helpers import (
    ChatRouteRuntime,
    build_parallel_agent_streams,
    build_share_url,
    build_single_agent_stream,
    create_session_record,
    decode_share_token,
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
    session_memory_payload,
    session_memory_updates,
    session_attachments_payload,
    session_update_requested,
    sse_streaming_response,
    summarize_session_memory_payload,
    update_session_memory_payload,
    workspaces_payload,
)
from backend.schemas.api_models import (
    ModelConfig,
    ImageInput,
    FileInput,
    ChatRequest,
    SingleChatRequest,
    CreateSessionRequest,
    UpdateSessionRequest,
    ReorderSessionsRequest,
    CreateBookmarkRequest,
    ShareLinkResponse,
    RevokeShareLinkResponse,
    ShareLinkAuditListResponse,
    SecurityStatusResponse,
    AuthWhoAmIResponse,
    AuthTokenCatalogResponse,
    SsoConfigResponse,
    SsoLoginResponse,
    SsoCallbackResponse,
    SecurityAuditEventListResponse,
    SecurityAuditCleanupResponse,
    SecurityAuditActionCatalogResponse,
    SecurityAuditSummaryResponse,
    SecurityAuditSiemExportResponse,
    SecurityAuditAggregateReportResponse,
    SecurityAuditArchivePolicyResponse,
    SecurityAuditLegalHoldResponse,
    RuntimeOperationsResponse,
    CreateWorkspaceRequest,
    UpdateWorkspaceRequest,
    SetMessageFeedbackRequest,
    TruncateSessionMessagesRequest,
    ImportSessionMessagesRequest,
    SetRetrievalFeedbackRequest,
    PinSessionMemoryRequest,
    UpdateSessionMemoryRequest,
    GenerateReportRequest,
    CreateDeckRequest,
    GenerateArtifactRequest,
    UpdateArtifactRequest,
    UpdateDeckRequest,
    RegenerateDeckSlideRequest,
    UpsertOrganizationRequest,
    UpsertUserRequest,
    SetMembershipRequest,
    SyncExternalIdentityRequest,
    OrganizationResponse,
    UserResponse,
    MembershipResponse,
    IdentityCatalogResponse,
    SyncExternalIdentityResponse,
    UpsertResourceGrantRequest,
    DeleteResourceGrantRequest,
    ResourceGrantResponse,
    ResourceGrantListResponse,
    ResourceAccessResponse,
    RolePermissionMatrixResponse,
    CreateTaskRequest,
    CreateMultiAgentWorkflowTaskRequest,
    ApprovalPolicyRequest,
    ApprovalTaskDecisionRequest,
)
from backend.routes import (
    build_access_router,
    build_chat_router,
    build_content_router,
    build_identity_router,
    build_kb_router,
    build_operations_router,
    build_prompt_router,
    build_security_router,
    build_session_router,
)
from backend.routes.operations_routes import run_integrator_scheduler_tick
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
from backend.stores import (
    SQLiteAppConfigStore,
    SQLiteSecurityAuditStore,
    SQLiteShareLinkStore,
    SQLiteTaskStore,
    TaskRecord,
    TaskStatus,
)
from backend.services.artifact_service import (
    SQLiteArtifactStore,
    artifact_export_formats,
    build_deck_artifact,
    build_report_artifact,
    build_research_archive_artifact,
    sync_deck_artifact,
)
from agent_mcp_helpers import (
    add_mcp_approved_connector,
    approve_runtime_mcp_connector as _approve_runtime_mcp_connector,
    clear_runtime_mcp_approved_connectors as _clear_runtime_mcp_approved_connectors,
    current_mcp_approved_connectors_payload as _current_mcp_approved_connectors_payload,
    default_mcp_server_names,
    get_mcp_runtime_health_history as _get_mcp_runtime_health_history,
    list_mcp_server_catalog,
    list_mcp_server_runtime_health as _list_mcp_server_runtime_health,
    normalize_mcp_approved_connectors,
    normalize_mcp_server_names,
    remove_mcp_approved_connector,
    revoke_runtime_mcp_connector as _revoke_runtime_mcp_connector,
    set_runtime_mcp_approved_connectors as _set_runtime_mcp_approved_connectors,
)
from backend.helpers.session_helpers import (
    build_answer_group_review_payload as _build_answer_group_review_payload,
    build_session_messages_payload as _build_session_messages_payload,
    collect_session_attachments as _collect_session_attachments,
    find_session_attachment as _find_session_attachment,
    render_shared_deck_html as _render_shared_deck_html,
    render_shared_session_html as _render_shared_session_html,
)
from backend.helpers.chat_input_helpers import (
    build_message_with_files as _build_message_with_files_impl,
    build_user_input as _build_user_input_impl,
    chat_file_suffix as _chat_file_suffix_impl,
    clip_attachment_preview_text as _clip_attachment_preview_text_impl,
    decode_data_url as _decode_data_url_impl,
    model_supports_images as _model_supports_images_impl,
    stringify_user_input as _stringify_user_input_impl,
    user_input_has_images as _user_input_has_images_impl,
    validate_chat_payload as _validate_chat_payload_impl,
)
from backend.helpers.chat_file_helpers import (
    ChatFileConfig,
    prepare_chat_files as _prepare_chat_files_impl,
)
from backend.helpers.agent_stream_helpers import (
    dashboard_prompt_excerpt,
    fail_dashboard_task,
    finalize_dashboard_task,
    resolve_non_stream_agent_result,
    stream_agent_item,
    task_created_event,
)
from backend.helpers.document_helpers import (
    build_chat_report_title,
    build_upload_documents_task_record,
    cleanup_temp_paths,
    populate_chat_report_presentation,
    retrieval_test_payload,
    safe_report_filename,
    stage_upload_files,
    stage_upload_files_with_limits,
    upload_documents_response,
)
from backend.helpers.deck_report_helpers import (
    apply_deck_update,
    build_create_deck_kwargs,
    build_regenerate_deck_kwargs,
    create_share_link_payload,
    export_deck_payload,
    replace_deck_slide,
    resolve_report_messages,
    report_download_payload,
    report_markdown_payload,
)
from backend.helpers.chat_stream_helpers import (
    answer_chunks,
    build_agent_config_payload,
    done_event as _done_event,
    panel_event as _panel_event,
    stream_parallel_sse,
    stream_single_sse,
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
from backend.helpers.kb_helpers import (
    filter_kb_chunks,
    kb_collect_chunks as _kb_collect_chunks,
    kb_docstore_dict as _kb_docstore_dict,
    kb_rebuild_from_documents as _kb_rebuild_from_documents,
    kb_safe_metadata as _kb_safe_metadata,
)
from backend.helpers.kb_chunk_route_helpers import (
    delete_kb_chunk_payload,
    list_kb_chunks_payload,
    update_kb_chunk_payload,
)
from backend.helpers.task_helpers import (
    contains_dashboard_card as _contains_dashboard_card,
    create_inline_task_record,
    prune_task_records,
    set_inline_task_state,
    should_start_dashboard_task as _should_start_dashboard_task,
    summarize_dashboard_task_error as _summarize_dashboard_task_error,
    summarize_dashboard_task_result as _summarize_dashboard_task_result,
)
from backend.helpers.task_runtime_helpers import (
    arq_runtime_config_for_tasks,
    attach_current_kb_status,
    enqueue_task,
    list_tasks_payload,
    task_runtime_health_summary,
    task_record_payload,
)
from backend.tasks.health import arq_queue_health_payload, task_stale_health_payload
from backend.helpers.task_execution_helpers import (
    persist_multi_agent_workflow_task_placeholder,
    persist_multi_agent_workflow_task_result,
    persist_web_research_task_placeholder,
    persist_web_research_task_result,
    run_analyze_knowledge_base_task,
    run_generate_deck_task,
    run_multi_agent_workflow_task,
    run_generate_report_task,
    run_placeholder_task,
    run_promote_attachment_to_kb_task,
    run_upload_documents_task,
    run_web_research_task,
)
from backend.services.deck_service import (
    DeckSlide,
    SQLiteDeckStore,
    build_deck,
    build_report_markdown,
    build_export_filename,
    ensure_deckable_chat,
    export_deck_to_pptx,
    normalize_deck_theme,
    regenerate_deck_slide,
)
from backend.logging_config import configure_logging
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

_log_format = configure_logging()
logger = logging.getLogger(__name__)
logger.info("日志格式: %s", _log_format)

_app_config_store = create_app_config_store()
MCP_APPROVED_CONNECTORS_CONFIG_KEY = "mcp_approved_connectors"
MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY = "mcp_runtime_health_history"


def _get_app_config_store() -> SQLiteAppConfigStore:
    return _app_config_store


def _mcp_runtime_health_history_limit(raw_limit: Any = None) -> int:
    try:
        limit = int(raw_limit or os.getenv("MCP_RUNTIME_HEALTH_HISTORY_LIMIT") or 20)
    except (TypeError, ValueError):
        limit = 20
    return min(200, max(1, limit))


def _sanitize_mcp_runtime_health_history_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
    servers = item.get("servers") if isinstance(item.get("servers"), list) else []
    try:
        timestamp = float(item.get("timestamp") or 0.0)
    except (TypeError, ValueError):
        timestamp = time.time()

    return {
        "timestamp": timestamp,
        "status": str(item.get("status") or "unknown"),
        "summary": {
            "total": int(summary.get("total", 0) or 0),
            "healthy": int(summary.get("healthy", 0) or 0),
            "unhealthy": int(summary.get("unhealthy", 0) or 0),
            "tool_count": int(summary.get("tool_count", 0) or 0),
            "status_counts": dict(summary.get("status_counts") or {}),
            "alert_count": int(summary.get("alert_count", 0) or 0),
            "unhealthy_connectors": list(summary.get("unhealthy_connectors") or []),
            "slow_connectors": list(summary.get("slow_connectors") or []),
        },
        "servers": [
            {
                "name": str(server.get("name") or ""),
                "status": str(server.get("status") or "unknown"),
                "healthy": bool(server.get("healthy")),
                "tool_count": int(server.get("tool_count", 0) or 0),
                "duration_ms": float(server.get("duration_ms", 0.0) or 0.0),
                "error": str(server.get("error") or "").strip() or None,
            }
            for server in servers
            if isinstance(server, dict)
        ],
    }


def _stored_mcp_runtime_health_history(limit: Any = None) -> list[dict[str, Any]]:
    safe_limit = _mcp_runtime_health_history_limit(limit)
    raw_value = _get_app_config_store().get_value(
        MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
        "[]",
    )
    try:
        decoded = json.loads(raw_value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        decoded = []
    if not isinstance(decoded, list):
        decoded = []

    history: list[dict[str, Any]] = []
    for item in decoded:
        sanitized = _sanitize_mcp_runtime_health_history_item(item)
        if sanitized is not None:
            history.append(sanitized)
        if len(history) >= safe_limit:
            break
    return history


def _persist_mcp_runtime_health_history_item(
    snapshot: dict[str, Any],
    history_limit: int,
) -> None:
    sanitized = _sanitize_mcp_runtime_health_history_item(snapshot)
    if sanitized is None:
        return
    safe_limit = _mcp_runtime_health_history_limit(history_limit)
    history = [sanitized, *_stored_mcp_runtime_health_history(safe_limit)]
    history = history[:safe_limit]
    _get_app_config_store().set(
        MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
        json.dumps(history, ensure_ascii=False, separators=(",", ":")),
    )


def get_mcp_runtime_health_history(limit: Any = 10) -> dict[str, Any]:
    safe_limit = _mcp_runtime_health_history_limit(limit)
    try:
        history = _stored_mcp_runtime_health_history(safe_limit)
        persistence_enabled = True
    except Exception:
        logger.exception("Failed to read persisted MCP runtime-health history")
        history = _get_mcp_runtime_health_history(safe_limit)
        persistence_enabled = False
    return {
        "history": history,
        "history_limit": safe_limit,
        "persistence": {
            "enabled": persistence_enabled,
            "config_key": MCP_RUNTIME_HEALTH_HISTORY_CONFIG_KEY,
        },
    }


async def list_mcp_server_runtime_health(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("history_recorder", _persist_mcp_runtime_health_history_item)
    kwargs.setdefault("history_reader", _stored_mcp_runtime_health_history)
    return await _list_mcp_server_runtime_health(**kwargs)


def _stored_mcp_approved_connectors() -> list[str]:
    raw_value = _get_app_config_store().get_value(
        MCP_APPROVED_CONNECTORS_CONFIG_KEY,
        "",
    )
    return normalize_mcp_approved_connectors(raw_value)


def _persist_mcp_approved_connectors(connector_names: Any) -> list[str]:
    names = normalize_mcp_approved_connectors(connector_names)
    if names:
        _get_app_config_store().set(
            MCP_APPROVED_CONNECTORS_CONFIG_KEY,
            ",".join(names),
        )
    else:
        _get_app_config_store().delete(MCP_APPROVED_CONNECTORS_CONFIG_KEY)
    _set_runtime_mcp_approved_connectors(names)
    return names


def _hydrate_runtime_mcp_approved_connectors_from_store() -> list[str]:
    names = _stored_mcp_approved_connectors()
    _set_runtime_mcp_approved_connectors(names)
    return names


def _mcp_approvals_payload_with_persistence() -> dict[str, Any]:
    persisted = _hydrate_runtime_mcp_approved_connectors_from_store()
    payload = _current_mcp_approved_connectors_payload()
    payload["persisted_connectors"] = persisted
    payload["persistence"] = {
        "enabled": True,
        "config_key": MCP_APPROVED_CONNECTORS_CONFIG_KEY,
    }
    return payload


def current_mcp_approved_connectors_payload() -> dict[str, Any]:
    return _mcp_approvals_payload_with_persistence()


def set_runtime_mcp_approved_connectors(raw_value: Any) -> list[str]:
    return _persist_mcp_approved_connectors(raw_value)


def clear_runtime_mcp_approved_connectors() -> list[str]:
    return _persist_mcp_approved_connectors([])


def approve_runtime_mcp_connector(connector_name: Any) -> dict[str, Any]:
    name = str(connector_name or "").strip()
    if not name:
        raise ValueError("connector name is required")
    before = _stored_mcp_approved_connectors()
    updated = _persist_mcp_approved_connectors(
        add_mcp_approved_connector(before, name)
    )
    payload = _mcp_approvals_payload_with_persistence()
    payload["connector"] = {
        "name": name,
        "changed": updated != before,
        "runtime_approved": name in payload["runtime_connectors"]
        or "*" in payload["runtime_connectors"],
        "effective_approved": name in payload["approved_connectors"]
        or "*" in payload["approved_connectors"],
    }
    return payload


def revoke_runtime_mcp_connector(connector_name: Any) -> dict[str, Any]:
    name = str(connector_name or "").strip()
    if not name:
        raise ValueError("connector name is required")
    before = _stored_mcp_approved_connectors()
    updated = _persist_mcp_approved_connectors(
        remove_mcp_approved_connector(before, name)
    )
    payload = _mcp_approvals_payload_with_persistence()
    payload["connector"] = {
        "name": name,
        "removed": updated != before,
        "runtime_approved": name in payload["runtime_connectors"]
        or "*" in payload["runtime_connectors"],
        "effective_approved": name in payload["approved_connectors"]
        or "*" in payload["approved_connectors"],
    }
    return payload


try:
    _hydrate_runtime_mcp_approved_connectors_from_store()
except Exception:
    logger.exception("Failed to hydrate persisted MCP connector approvals")


def _get_identity_store():
    return _identity_store


def _get_resource_access_store():
    return _resource_access_store


def _stored_config_value(key: str, default: str = "") -> str:
    return stored_config_value(_get_app_config_store(), logger, key, default)


def _stored_sso_config_value(field: str) -> str | None:
    spec = _SSO_CONFIG_FIELDS.get(field)
    if spec is None:
        return None
    _, _, config_key, _ = spec
    try:
        record = _get_app_config_store().get(config_key)
    except Exception:
        logger.exception("Failed to read persisted SSO config field=%s", field)
        return None
    return record.value if record is not None else None


def _effective_sso_config_value(field: str) -> str:
    spec = _SSO_CONFIG_FIELDS[field]
    attr_name, _, _, default = spec
    current_value = str(globals().get(attr_name, default) or "").strip()
    initial_value = _INITIAL_SSO_CONFIG_VALUES.get(attr_name, str(default)).strip()
    if current_value != initial_value:
        return current_value
    stored_value = _stored_sso_config_value(field)
    if stored_value is not None:
        return str(stored_value or "").strip()
    return current_value


def _effective_sso_session_ttl_seconds() -> int:
    raw_value = _effective_sso_config_value("session_ttl_seconds")
    try:
        return max(300, int(raw_value or str(8 * 60 * 60)))
    except (TypeError, ValueError):
        return 8 * 60 * 60


def _sync_runtime_secret_from_store(env_name: str, config_key: str) -> str:
    return sync_runtime_secret_from_store(
        _get_app_config_store(),
        logger,
        env_name,
        config_key,
    )


def _normalize_cloud_model_api_key_ref(value: Any, *, allow_empty: bool = False) -> str:
    return normalize_cloud_model_api_key_ref(value, allow_empty=allow_empty)


def _cloud_model_api_key_config_key(api_key_ref: str) -> str:
    return cloud_model_api_key_config_key(api_key_ref)


def _upsert_cloud_model_api_key(api_key_ref: str | None, api_key: str) -> str:
    return upsert_cloud_model_api_key(_get_app_config_store(), api_key_ref, api_key)


def _delete_cloud_model_api_key(api_key_ref: str) -> bool:
    return delete_cloud_model_api_key(_get_app_config_store(), api_key_ref)


def _resolve_model_api_key(mc: "ModelConfig | dict[str, Any]") -> str:
    return resolve_model_api_key(
        _get_app_config_store(),
        logger,
        mc,
        model_config_payload=_model_config_payload,
    )


async def _validate_tavily_api_key(api_key: str) -> None:
    await validate_tavily_api_key(api_key)


_sync_runtime_secret_from_store("TAVILY_API_KEY", "tavily_api_key")


def _env_int_setting(
    name: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> tuple[int, str]:
    raw = os.getenv(name)
    value = int(default)
    source = "default"

    if raw is not None:
        try:
            value = int(str(raw).strip())
            source = "env"
        except (TypeError, ValueError):
            logger.warning("Invalid %s=%r; using default=%s", name, raw, default)
            value = int(default)
            source = "invalid_env"

    if minimum is not None and value < minimum:
        logger.warning(
            "%s=%r is below minimum=%s; using %s", name, raw, minimum, minimum
        )
        value = int(minimum)
        source = f"{source}_clamped"

    if maximum is not None and value > maximum:
        logger.warning(
            "%s=%r is above maximum=%s; using %s", name, raw, maximum, maximum
        )
        value = int(maximum)
        source = f"{source}_clamped"

    return int(value), source


def _env_bool_setting(name: str, default: bool) -> tuple[bool, str]:
    raw = os.getenv(name)
    if raw is None:
        return bool(default), "default"

    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True, "env"
    if normalized in {"0", "false", "no", "off"}:
        return False, "env"

    logger.warning("Invalid %s=%r; using default=%s", name, raw, default)
    return bool(default), "invalid_env"


def _integrator_scheduler_config_from_env() -> dict[str, Any]:
    enabled, enabled_source = _env_bool_setting(
        "INTEGRATOR_SCHEDULER_ENABLED",
        False,
    )
    interval_seconds, interval_source = _env_int_setting(
        "INTEGRATOR_SCHEDULER_INTERVAL_SECONDS",
        60,
        minimum=1,
    )
    return {
        "enabled": enabled,
        "enabled_source": enabled_source,
        "interval_seconds": interval_seconds,
        "interval_source": interval_source,
    }


PROJECT_ROOT = BACKEND_DIR.parent
UPLOAD_CHUNK_SIZE = 1024 * 1024
TASK_HISTORY_LIMIT = 200
TASK_HISTORY_TTL_SECONDS = int(os.getenv("TASK_HISTORY_TTL_SECONDS", str(6 * 60 * 60)))
TASK_BACKEND = os.getenv("TASK_BACKEND", "memory").strip().lower() or "memory"
enqueue_external_task = None
KB_METADATA_TTL_SECONDS = 30
CHAT_FILE_CONTEXT_START_MARKER = "[[CHAT_FILE_CONTEXT_START]]"
CHAT_FILE_CONTEXT_END_MARKER = "[[CHAT_FILE_CONTEXT_END]]"
CHAT_FILE_MAX_COUNT = int(os.getenv("CHAT_FILE_MAX_COUNT", "6"))
CHAT_FILE_MAX_BYTES = int(os.getenv("CHAT_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
CHAT_FILE_MAX_CHARS_PER_FILE = int(os.getenv("CHAT_FILE_MAX_CHARS_PER_FILE", "8000"))
CHAT_FILE_MAX_TOTAL_CHARS = int(os.getenv("CHAT_FILE_MAX_TOTAL_CHARS", "24000"))
CHAT_ATTACHMENT_PREVIEW_CHARS = int(os.getenv("CHAT_ATTACHMENT_PREVIEW_CHARS", "4000"))
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
SECURITY_AUDIT_HISTORY_LIMIT, SECURITY_AUDIT_HISTORY_LIMIT_SOURCE = _env_int_setting(
    "SECURITY_AUDIT_HISTORY_LIMIT",
    2000,
    minimum=1,
)
(
    REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS,
    REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE,
) = _env_int_setting(
    "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS",
    60,
    minimum=1,
)
(
    REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS,
    REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS_SOURCE,
) = _env_int_setting(
    "REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS",
    30,
    minimum=1,
)
REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED = str(
    os.getenv("REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED", "true") or "true"
).strip().lower() in {"1", "true", "yes", "on"}
RUNTIME_RECENT_ERROR_LIMIT = 20
DEEP_RESEARCH_MAX_CONCURRENCY, DEEP_RESEARCH_MAX_CONCURRENCY_SOURCE = _env_int_setting(
    "DEEP_RESEARCH_MAX_CONCURRENCY",
    2,
    minimum=1,
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


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def _cors_settings() -> tuple[list[str], bool]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return (
            [
                "http://127.0.0.1:5173",
                "http://localhost:5173",
                "http://127.0.0.1:8000",
                "http://localhost:8000",
            ],
            True,
        )

    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if "*" in origins:
        return ["*"], False
    return origins, True


def _is_loopback_host(host: Optional[str]) -> bool:
    if not host:
        return False
    if host in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _hash_secret(secret: str) -> str:
    return security_runtime._hash_secret(sys.modules[__name__], secret)


def _token_fingerprint(token: str) -> str:
    return security_runtime._token_fingerprint(sys.modules[__name__], token)


def _token_preview(token: str) -> str:
    return security_runtime._token_preview(sys.modules[__name__], token)


def _auth_token_preview(token: str) -> str:
    return security_runtime._auth_token_preview(sys.modules[__name__], token)


def _request_client_ip(request: Request) -> str:
    return security_runtime._request_client_ip(sys.modules[__name__], request)


def _request_user_agent(request: Request) -> str:
    return security_runtime._request_user_agent(sys.modules[__name__], request)


def _request_is_local(request: Request) -> bool:
    return security_runtime._request_is_local(sys.modules[__name__], request)


def _current_admin_api_token() -> str:
    return security_runtime._current_admin_api_token(sys.modules[__name__])


def _normalize_auth_role(role: Any, *, default: str = DEFAULT_AUTH_ROLE) -> str:
    return security_runtime._normalize_auth_role(
        sys.modules[__name__], role, default=default
    )


def _role_rank(role: str) -> int:
    return security_runtime._role_rank(sys.modules[__name__], role)


def _sanitize_log_value(value: Any, *, max_length: int = 256) -> str:
    return security_runtime._sanitize_log_value(
        sys.modules[__name__], value, max_length=max_length
    )


def _auth_capabilities_for_role(role: str) -> list[str]:
    return security_runtime._auth_capabilities_for_role(sys.modules[__name__], role)


def _auth_token_is_weak(token: Any) -> bool:
    return security_runtime._auth_token_is_weak(sys.modules[__name__], token)


def _auth_token_hygiene_summary(
    auth_records: list[dict[str, str]] | None = None,
) -> dict[str, int | bool]:
    return security_runtime._auth_token_hygiene_summary(
        sys.modules[__name__], auth_records
    )


def _configured_auth_token_records() -> list[dict[str, str]]:
    return security_runtime._configured_auth_token_records(sys.modules[__name__])


def _configured_auth_token_map() -> dict[str, dict[str, str]]:
    return security_runtime._configured_auth_token_map(sys.modules[__name__])


def _extract_request_token(request: Request) -> str:
    return security_runtime._extract_request_token(sys.modules[__name__], request)


def _extract_admin_token(request: Request) -> str:
    return security_runtime._extract_admin_token(sys.modules[__name__], request)


def _request_auth_mode(request: Request) -> str:
    return security_runtime._request_auth_mode(sys.modules[__name__], request)


def _admin_auth_mode(request: Request) -> str:
    return security_runtime._admin_auth_mode(sys.modules[__name__], request)


def _resolve_request_auth(request: Request) -> dict[str, Any]:
    return security_runtime._resolve_request_auth(sys.modules[__name__], request)


def _request_user_id(request: Request) -> str:
    return security_runtime._request_user_id(sys.modules[__name__], request)


def _request_user_role(request: Request) -> str:
    return security_runtime._request_user_role(sys.modules[__name__], request)


def _request_auth_source(request: Request) -> str:
    return security_runtime._request_auth_source(sys.modules[__name__], request)


def _sanitize_request_path(path: str) -> str:
    return security_runtime._sanitize_request_path(sys.modules[__name__], path)


def _remote_management_rate_limit_applies(request: Request) -> bool:
    return security_runtime._remote_management_rate_limit_applies(
        sys.modules[__name__], request
    )


def _remote_management_rate_limit_principal(request: Request) -> str:
    return security_runtime._remote_management_rate_limit_principal(
        sys.modules[__name__], request
    )


def _ceil_seconds(seconds: float) -> int:
    return security_runtime._ceil_seconds(sys.modules[__name__], seconds)


def _consume_remote_management_rate_limit(request: Request) -> dict[str, Any] | None:
    return security_runtime._consume_remote_management_rate_limit(
        sys.modules[__name__], request
    )


def _current_share_link_secret() -> str:
    return security_runtime._current_share_link_secret(sys.modules[__name__])


def _share_link_secret_is_weak() -> bool:
    return security_runtime._share_link_secret_is_weak(sys.modules[__name__])


def _require_remote_role(
    request: Request, *, minimum_role: str = "admin"
) -> dict[str, Any]:
    return security_runtime._require_remote_role(
        sys.modules[__name__], request, minimum_role=minimum_role
    )


def _require_remote_viewer(request: Request) -> dict[str, Any]:
    return security_runtime._require_remote_viewer(sys.modules[__name__], request)


def _require_remote_editor(request: Request) -> dict[str, Any]:
    return security_runtime._require_remote_editor(sys.modules[__name__], request)


def _require_remote_admin(request: Request) -> dict[str, Any]:
    return security_runtime._require_remote_admin(sys.modules[__name__], request)


def _require_remote_share_secret(request: Request) -> None:
    return security_runtime._require_remote_share_secret(sys.modules[__name__], request)


def _content_hash(value: Any) -> str:
    return security_runtime._content_hash(sys.modules[__name__], value)


def _audit_security_event(
    action: str, request: Request, *, result: str = "ok", details: str = ""
) -> None:
    return security_runtime._audit_security_event(
        sys.modules[__name__], action, request, result=result, details=details
    )


def _share_link_audit_payload(
    record: Any, *, now: Optional[float] = None
) -> dict[str, Any]:
    return security_runtime._share_link_audit_payload(
        sys.modules[__name__], record, now=now
    )


def _security_status_payload() -> dict[str, Any]:
    return security_runtime._security_status_payload(sys.modules[__name__])


def _auth_token_catalog_payload() -> dict[str, Any]:
    return security_runtime._auth_token_catalog_payload(sys.modules[__name__])


def _sso_config_payload() -> dict[str, Any]:
    return _build_sso_config_payload(
        provider=_effective_sso_config_value("provider"),
        issuer_url=_effective_sso_config_value("issuer_url"),
        authorization_endpoint=_effective_sso_config_value("authorization_endpoint"),
        token_endpoint=_effective_sso_config_value("token_endpoint"),
        jwks_url=_effective_sso_config_value("jwks_url"),
        client_id=_effective_sso_config_value("client_id"),
        client_secret=_effective_sso_config_value("client_secret"),
        allowed_domains=_effective_sso_config_value("allowed_domains"),
        scopes=_effective_sso_config_value("scopes"),
        default_role=_normalize_auth_role(
            _effective_sso_config_value("default_role"),
            default=DEFAULT_AUTH_ROLE,
        ),
        session_ttl_seconds=_effective_sso_session_ttl_seconds(),
    )


def _normalize_sso_config_update(field: str, value: Any) -> str:
    normalized = str(value or "").strip()
    if field == "provider":
        normalized = normalized.lower() or "none"
        if normalized not in {"none", "oidc"}:
            raise HTTPException(status_code=400, detail="SSO provider must be none or oidc")
    elif field == "default_role":
        normalized = _normalize_auth_role(normalized, default=DEFAULT_AUTH_ROLE)
    elif field == "session_ttl_seconds":
        try:
            ttl_seconds = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail="SSO session TTL must be an integer number of seconds",
            ) from exc
        if ttl_seconds < 300 or ttl_seconds > 7 * 24 * 60 * 60:
            raise HTTPException(
                status_code=400,
                detail="SSO session TTL must be between 300 and 604800 seconds",
            )
        normalized = str(ttl_seconds)
    return normalized


def _set_sso_config_field(field: str, value: str) -> None:
    attr_name, env_name, config_key, _ = _SSO_CONFIG_FIELDS[field]
    if value:
        _get_app_config_store().set(config_key, value)
        os.environ[env_name] = value
    else:
        _get_app_config_store().delete(config_key)
        os.environ.pop(env_name, None)
    if attr_name == "SSO_SESSION_TTL_SECONDS":
        globals()[attr_name] = int(value or str(8 * 60 * 60))
    else:
        globals()[attr_name] = value


def _save_sso_config_payload(body: Any) -> dict[str, Any]:
    data = _base_model_payload(body)
    clear_client_secret = bool(data.pop("clear_client_secret", False))
    for field in (
        "provider",
        "issuer_url",
        "authorization_endpoint",
        "token_endpoint",
        "jwks_url",
        "client_id",
        "allowed_domains",
        "scopes",
        "default_role",
        "session_ttl_seconds",
    ):
        if field not in data or data[field] is None:
            continue
        _set_sso_config_field(field, _normalize_sso_config_update(field, data[field]))

    client_secret = data.get("client_secret")
    if clear_client_secret:
        _set_sso_config_field("client_secret", "")
    elif client_secret is not None and str(client_secret or "").strip():
        _set_sso_config_field("client_secret", str(client_secret or "").strip())

    return _sso_config_payload()


def _sso_callback_url(request: Request) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/api/auth/sso/callback"


def _sso_callback_url_for_mode(request: Request, response_mode: str = "") -> str:
    callback_url = _sso_callback_url(request)
    if str(response_mode or "").strip().lower() == "fragment":
        return f"{callback_url}?response_mode=fragment"
    return callback_url


def _pkce_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _prune_sso_login_states(now: float | None = None) -> None:
    current_time = time.time() if now is None else float(now)
    expired_before = current_time - float(SSO_LOGIN_STATE_TTL_SECONDS)
    with _sso_login_states_lock:
        expired = [
            state
            for state, record in _sso_login_states.items()
            if float(record.get("created_at", 0.0) or 0.0) <= expired_before
        ]
        for state in expired:
            _sso_login_states.pop(state, None)


def _prune_sso_sessions(now: float | None = None) -> None:
    current_time = time.time() if now is None else float(now)
    try:
        _get_sso_session_store().prune(now=current_time)
    except Exception:
        logger.exception("Failed to prune persisted SSO sessions")
    with _sso_sessions_lock:
        expired = [
            token
            for token, record in _sso_sessions.items()
            if float(record.get("expires_at", 0.0) or 0.0) <= current_time
        ]
        for token in expired:
            _sso_sessions.pop(token, None)


def _issue_sso_session_token(*, user_id: str, role: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("user_id is required")
    normalized_role = _normalize_auth_role(role, default=DEFAULT_AUTH_ROLE)
    token = f"sso_{secrets.token_urlsafe(32)}"
    created_at = time.time()
    expires_at = created_at + float(_effective_sso_session_ttl_seconds())
    _prune_sso_sessions()
    session_record = {
        "user_id": normalized_user_id,
        "role": normalized_role,
        "auth_source": "sso_oidc",
        "expires_at": expires_at,
        "created_at": created_at,
    }
    try:
        _get_sso_session_store().save(
            token_hash=_sso_session_token_hash(token),
            user_id=normalized_user_id,
            role=normalized_role,
            auth_source="sso_oidc",
            created_at=created_at,
            expires_at=expires_at,
        )
    except Exception as exc:
        raise RuntimeError("Failed to persist SSO session") from exc
    with _sso_sessions_lock:
        _sso_sessions[token] = session_record
    return {
        "token": token,
        "expires_at": expires_at,
        "role": normalized_role,
    }


def _resolve_sso_session_token(token: str) -> dict[str, str] | None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None
    _prune_sso_sessions()
    token_hash = _sso_session_token_hash(normalized_token)
    try:
        persisted = _get_sso_session_store().get_active(token_hash)
    except Exception:
        logger.exception("Failed to resolve persisted SSO session")
        persisted = None
    if persisted is not None:
        return {
            "user_id": str(persisted.user_id or "").strip(),
            "role": str(persisted.role or DEFAULT_AUTH_ROLE).strip(),
            "auth_source": str(persisted.auth_source or "sso_oidc").strip(),
        }
    with _sso_sessions_lock:
        record = _sso_sessions.get(normalized_token)
        if record is None:
            return None
        return {
            "user_id": str(record.get("user_id") or "").strip(),
            "role": str(record.get("role") or DEFAULT_AUTH_ROLE).strip(),
            "auth_source": str(record.get("auth_source") or "sso_oidc").strip(),
        }


def _sso_login_payload(request: Request, response_mode: str = "") -> dict[str, Any]:
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(48)
    payload = _build_sso_login_payload(
        provider=_effective_sso_config_value("provider"),
        authorization_endpoint=_effective_sso_config_value("authorization_endpoint"),
        client_id=_effective_sso_config_value("client_id"),
        redirect_uri=_sso_callback_url_for_mode(request, response_mode=response_mode),
        state=state,
        nonce=nonce,
        code_challenge=_pkce_code_challenge(code_verifier),
        scopes=_effective_sso_config_value("scopes"),
    )
    _prune_sso_login_states()
    with _sso_login_states_lock:
        _sso_login_states[state] = {
            "created_at": time.time(),
            "nonce": nonce,
            "code_verifier": code_verifier,
            "redirect_uri": payload["redirect_uri"],
        }
    return payload


async def _exchange_oidc_code(
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    normalized_code = str(code or "").strip()
    if not normalized_code:
        raise ValueError("authorization code is required")
    if _effective_sso_config_value("provider").lower() != "oidc":
        raise ValueError("SSO_PROVIDER must be oidc")
    token_endpoint = _effective_sso_config_value("token_endpoint")
    if not token_endpoint:
        raise RuntimeError("OIDC_TOKEN_ENDPOINT is required")
    data = {
        "grant_type": "authorization_code",
        "code": normalized_code,
        "redirect_uri": str(redirect_uri or "").strip(),
        "client_id": _effective_sso_config_value("client_id"),
        "code_verifier": str(code_verifier or "").strip(),
    }
    client_secret = _effective_sso_config_value("client_secret")
    if client_secret:
        data["client_secret"] = client_secret
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                token_endpoint,
                data=data,
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise RuntimeError("OIDC token exchange failed") from exc
    if response.status_code >= 400:
        raise RuntimeError("OIDC token exchange failed")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("OIDC token response is not JSON") from exc
    if not str(payload.get("id_token") or "").strip():
        raise RuntimeError("OIDC token response missing id_token")
    return payload


def _verify_oidc_id_token(id_token: str, *, nonce: str) -> dict[str, Any]:
    normalized_id_token = str(id_token or "").strip()
    if not normalized_id_token:
        raise ValueError("id_token is required")
    jwks_url = _effective_sso_config_value("jwks_url")
    if not jwks_url:
        raise RuntimeError("OIDC_JWKS_URL is required")
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        raise RuntimeError("PyJWT[crypto] is required for OIDC ID token verification") from exc
    try:
        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(
            normalized_id_token
        )
        claims = jwt.decode(
            normalized_id_token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=_effective_sso_config_value("client_id"),
            issuer=_effective_sso_config_value("issuer_url"),
        )
    except Exception as exc:
        raise ValueError("OIDC ID token verification failed") from exc
    expected_nonce = str(nonce or "").strip()
    if expected_nonce and str(claims.get("nonce") or "").strip() != expected_nonce:
        raise ValueError("OIDC nonce mismatch")
    return dict(claims)


async def _sso_callback_payload(
    request: Request,
    *,
    code: str,
    state: str,
) -> dict[str, Any]:
    normalized_state = str(state or "").strip()
    if not normalized_state:
        raise ValueError("state is required")
    _prune_sso_login_states()
    with _sso_login_states_lock:
        state_record = _sso_login_states.pop(normalized_state, None)
    if state_record is None:
        raise ValueError("Invalid or expired SSO state")

    token_payload = await _exchange_oidc_code(
        code=code,
        redirect_uri=str(state_record.get("redirect_uri") or _sso_callback_url(request)),
        code_verifier=str(state_record.get("code_verifier") or ""),
    )
    claims = _verify_oidc_id_token(
        str(token_payload.get("id_token") or ""),
        nonce=str(state_record.get("nonce") or ""),
    )
    sync_request = SyncExternalIdentityRequest(
        claims=claims,
        provider=_effective_sso_config_value("provider") or "oidc",
    )
    payload = _sync_external_identity_payload(sync_request)
    payload["auth_source"] = "oidc"
    payload["token_type"] = str(token_payload.get("token_type") or "")
    expires_in = token_payload.get("expires_in")
    payload["expires_in"] = int(expires_in) if expires_in is not None else None
    session = _issue_sso_session_token(
        user_id=str(payload["user"]["user_id"] or ""),
        role=_effective_sso_config_value("default_role"),
    )
    payload["app_session_token"] = session["token"]
    payload["app_session_expires_at"] = session["expires_at"]
    payload["role"] = session["role"]
    return payload


def _sync_external_identity_payload(body: SyncExternalIdentityRequest) -> dict[str, Any]:
    allowed_domains = body.allowed_domains or [
        item.strip()
        for item in _effective_sso_config_value("allowed_domains").split(",")
        if item.strip()
    ]
    return _sync_external_identity(
        identity_store=_get_identity_store(),
        claims=body.claims,
        provider=body.provider or _effective_sso_config_value("provider") or "oidc",
        allowed_domains=allowed_domains,
        default_org_id=body.default_org_id,
        default_role=body.default_role,
        group_org_map=body.group_org_map,
        group_role_map=dict(body.group_role_map),
        now=time.time,
    )


def _security_audit_events_payload(
    *,
    limit: int = 50,
    action: str = "",
    result: str = "",
    category: str = "",
    user_id: str = "",
    since: Any = None,
    until: Any = None,
) -> dict[str, Any]:
    return security_runtime._security_audit_events_payload(
        sys.modules[__name__],
        limit=limit,
        action=action,
        result=result,
        category=category,
        user_id=user_id,
        since=since,
        until=until,
    )


def _security_audit_action_catalog_payload(*, category: str = "") -> dict[str, Any]:
    return _build_security_audit_action_catalog_payload(category=category)


def _security_audit_summary_payload(
    *, category: str = "", limit: int = 0
) -> dict[str, Any]:
    return security_runtime._security_audit_summary_payload(
        sys.modules[__name__],
        category=category,
        limit=limit,
    )


def _security_audit_siem_export_payload(
    *,
    format: str = "json",
    limit: int = 100,
    action: str = "",
    result: str = "",
    category: str = "",
    user_id: str = "",
    since: Any = None,
    until: Any = None,
) -> dict[str, Any]:
    return security_runtime._security_audit_siem_export_payload(
        sys.modules[__name__],
        format=format,
        limit=limit,
        action=action,
        result=result,
        category=category,
        user_id=user_id,
        since=since,
        until=until,
    )


def _security_audit_aggregate_report_payload(
    *,
    limit: int = 0,
    action: str = "",
    result: str = "",
    category: str = "",
    user_id: str = "",
    since: Any = None,
    until: Any = None,
) -> dict[str, Any]:
    return security_runtime._security_audit_aggregate_report_payload(
        sys.modules[__name__],
        limit=limit,
        action=action,
        result=result,
        category=category,
        user_id=user_id,
        since=since,
        until=until,
    )


def _security_audit_archive_policy_payload(
    *,
    mode: str = "preview",
    retention_days: int = 365,
    limit: int = 100,
    legal_hold: bool = False,
) -> dict[str, Any]:
    return security_runtime._security_audit_archive_policy_payload(
        sys.modules[__name__],
        mode=mode,
        retention_days=retention_days,
        limit=limit,
        legal_hold=legal_hold,
    )


def _security_audit_legal_hold_payload(
    *, request_id: str, legal_hold: bool = True
) -> dict[str, Any]:
    return security_runtime._security_audit_legal_hold_payload(
        sys.modules[__name__],
        request_id=request_id,
        legal_hold=legal_hold,
    )


def _role_permission_matrix_payload() -> dict[str, Any]:
    return _build_role_permission_matrix_payload()


def _cleanup_security_audit_events(
    *, keep_latest: int = 0, dry_run: bool = False
) -> dict[str, Any]:
    return security_runtime._cleanup_security_audit_events(
        sys.modules[__name__],
        keep_latest=keep_latest,
        dry_run=dry_run,
    )


def _runtime_status_class(status_code: int) -> str:
    return runtime_status_class(status_code)


def _record_runtime_request(
    *, status_code: int, timestamp: float | None = None
) -> None:
    record_runtime_request(
        _runtime_metrics,
        _runtime_metrics_lock,
        status_code=status_code,
        timestamp=timestamp,
    )


def _record_runtime_error(
    *,
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    timestamp: float | None = None,
) -> None:
    record_runtime_error(
        _runtime_metrics,
        _runtime_metrics_lock,
        request=request,
        status_code=status_code,
        error_code=error_code,
        message=message,
        sanitize_request_path=_sanitize_request_path,
        sanitize_log_value=_sanitize_log_value,
        recent_error_limit=RUNTIME_RECENT_ERROR_LIMIT,
        timestamp=timestamp,
    )


def _runtime_request_metrics_payload() -> dict[str, Any]:
    return runtime_request_metrics_payload(_runtime_metrics, _runtime_metrics_lock)


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


def _sso_session_token_hash(token: str) -> str:
    normalized_token = str(token or "").strip()
    return hashlib.sha256(normalized_token.encode("utf-8")).hexdigest()


def _get_sso_session_store():
    global _sso_session_store
    if _sso_session_store is None:
        with _sso_session_store_init_lock:
            if _sso_session_store is None:
                _sso_session_store = create_sso_session_store()
    return _sso_session_store


async def _runtime_task_summary_payload() -> dict[str, Any]:
    async with _tasks_lock:
        records = list(_tasks.values())
    latest_task_updated_at: float | None = None
    counts = {
        TaskStatus.PENDING.value: 0,
        TaskStatus.RUNNING.value: 0,
        TaskStatus.COMPLETED.value: 0,
        TaskStatus.FAILED.value: 0,
    }
    for record in records:
        status = (
            record.status.value
            if isinstance(record.status, TaskStatus)
            else str(record.status or "").strip().lower()
        )
        counts[status] = int(counts.get(status, 0)) + 1
        updated_at = float(getattr(record, "updated_at", 0) or 0)
        if updated_at > 0 and (
            latest_task_updated_at is None or updated_at > latest_task_updated_at
        ):
            latest_task_updated_at = updated_at
    health = task_stale_health_payload(records)
    if str(TASK_BACKEND or "").strip().lower() in {"arq", "redis"}:
        health["queue"] = await arq_queue_health_payload()
        health["runtime"] = arq_runtime_config_for_tasks()
    health["summary"] = task_runtime_health_summary(health)
    return {
        "in_memory_total": len(records),
        "pending": counts[TaskStatus.PENDING.value],
        "running": counts[TaskStatus.RUNNING.value],
        "completed": counts[TaskStatus.COMPLETED.value],
        "failed": counts[TaskStatus.FAILED.value],
        "latest_task_updated_at": latest_task_updated_at,
        "health": health,
    }


async def _runtime_operations_payload() -> dict[str, Any]:
    metrics = _runtime_request_metrics_payload()
    task_summary = await _runtime_task_summary_payload()
    uptime_seconds = round(max(0.0, time.time() - _runtime_started_at), 3)
    llm_metrics = runtime_llm_metrics_payload()
    return {
        "started_at": _runtime_started_at,
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
        "security": _security_status_payload(),
    }


def _resolve_project_subdir(candidate: str) -> Path:
    raw_path = Path(candidate).expanduser()
    if not raw_path.is_absolute():
        raw_path = PROJECT_ROOT / raw_path
    resolved = raw_path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=403, detail="不允许访问项目目录之外的路径"
        ) from exc
    if resolved == PROJECT_ROOT:
        raise HTTPException(status_code=403, detail="不允许直接操作项目根目录")
    return resolved


def _faiss_safe_store_path(path: str | Path) -> str:
    target = Path(path)
    if not target.is_absolute():
        target = (PROJECT_ROOT / target).resolve()
    else:
        target = target.resolve()

    try:
        return str(target.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(target)


def _resolve_deletable_knowledge_base(candidate: str) -> Path:
    target_path = _resolve_project_subdir(candidate)

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="知识库路径不存在")
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="知识库路径必须是目录")
    if not (target_path / "index.faiss").is_file():
        raise HTTPException(
            status_code=400,
            detail="只能删除包含 index.faiss 的目录",
        )

    return target_path


def _active_vector_store_id() -> str | None:
    _, vector_store_path, _ = _resolve_active_prompt_runtime(True)
    return vector_store_path


def _resolve_active_prompt_runtime(
    knowledge_base_enabled: bool,
) -> tuple[Optional[str], Optional[str], dict[str, Any]]:
    from chat_store import get_active_system_prompt

    active_prompt = get_active_system_prompt() or {}

    system_prompt_content_raw = active_prompt.get("content")
    system_prompt_content = (
        str(system_prompt_content_raw).strip()
        if isinstance(system_prompt_content_raw, str)
        else ""
    ) or None

    vector_store_path = str(active_prompt.get("vector_store_id") or "").strip() or None
    if not knowledge_base_enabled:
        vector_store_path = None

    dashboard_template_raw = active_prompt.get("dashboard_template", {})
    dashboard_template = (
        dict(dashboard_template_raw) if isinstance(dashboard_template_raw, dict) else {}
    )

    return system_prompt_content, vector_store_path, dashboard_template


def _dashboard_feature_enabled(dashboard_template: Optional[dict[str, Any]]) -> bool:
    if not isinstance(dashboard_template, dict):
        return True
    return dashboard_template.get("enabled") is not False


def _effective_vector_store_path(candidate: Optional[str] = None) -> str:
    raw = str(candidate or "").strip()
    if not raw:
        raw = _active_vector_store_id() or os.getenv(
            "VECTOR_STORE_PATH", "./vector_store"
        )
    return _faiss_safe_store_path(_resolve_project_subdir(raw))


def _require_workspace_session(
    session_id: str,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    from chat_store import DEFAULT_WORKSPACE_ID, get_session, get_workspace

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


def _build_download_content_disposition(filename: str) -> str:
    raw_filename = str(filename or "").strip() or "download"
    ascii_only = all(ord(char) < 128 for char in raw_filename)
    if ascii_only:
        escaped = raw_filename.replace("\\", "\\\\").replace('"', r"\"")
        return f'attachment; filename="{escaped}"'

    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_filename).strip("._")
    if not ascii_fallback:
        ascii_fallback = "download"
    encoded = quote(raw_filename, safe="")
    return f"attachment; filename={ascii_fallback}; filename*=UTF-8''{encoded}"


ALLOW_REMOTE_CLIENTS = _env_flag("ALLOW_REMOTE_CLIENTS", False)
_cors_origins, _cors_allow_credentials = _cors_settings()
_REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES = (
    "/api/security/",
    "/api/auth/",
    "/api/access/",
    "/api/identity",
    "/api/operations/runtime",
    "/api/config",
    "/api/prompts",
    "/api/share-links",
    "/api/agents/reset",
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


def _new_runtime_metrics_state() -> dict[str, Any]:
    return new_runtime_metrics_state()


_runtime_metrics = _new_runtime_metrics_state()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _artifact_payload(artifact: Any) -> dict[str, Any]:
    payload = artifact.model_dump(mode="json")
    payload["available_formats"] = artifact_export_formats(artifact)
    return payload


def _sync_deck_artifacts(deck: Any) -> None:
    deck_id = str(getattr(deck, "deck_id", "") or "").strip()
    if not deck_id:
        return
    for artifact in _artifact_store.list_by_linked_resource("deck", deck_id):
        sync_deck_artifact(artifact, deck)
        _artifact_store.save(artifact)


@app.middleware("http")
async def restrict_remote_clients(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    try:
        if ALLOW_REMOTE_CLIENTS:
            rate_limit_payload = _consume_remote_management_rate_limit(request)
            request.state.remote_management_rate_limit = rate_limit_payload
            if rate_limit_payload and not rate_limit_payload["allowed"]:
                _audit_security_event(
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
            client_host = request.client.host if request.client else None
            if _is_loopback_host(client_host):
                response = await call_next(request)
            else:
                logger.warning(
                    "Blocked non-local request request_id=%s host=%s path=%s",
                    request_id,
                    client_host,
                    _sanitize_request_path(request.url.path),
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
    _record_runtime_request(
        status_code=int(response.status_code), timestamp=time.time()
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
        _sanitize_request_path(request.url.path),
        response.status_code,
        process_time_ms,
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err = _classify_error(exc)
    request_id = getattr(request.state, "request_id", "")
    logger.exception(
        "Unhandled exception request_id=%s on %s", request_id, request.url.path
    )
    _record_runtime_error(
        request=request,
        status_code=500,
        error_code=str(err["code"] or "").strip(),
        message=str(exc or err["message"]).strip() or str(err["message"]).strip(),
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


def _classify_error(e: Exception) -> dict:
    """将异常映射为用户友好的错误信息 + 错误码 + 恢复建议"""
    msg = str(e)
    if isinstance(e, ConnectionError) or any(
        kw in msg
        for kw in ("Connection refused", "ConnectError", "connect ECONNREFUSED")
    ):
        return {
            "code": "MODEL_UNAVAILABLE",
            "message": "模型服务暂时不可用",
            "suggestion": "请检查 Ollama 是否已启动，或稍后重试",
        }
    if any(
        kw in msg
        for kw in ("API Key", "api_key", "401", "Unauthorized", "authentication")
    ):
        return {
            "code": "AUTH_FAILED",
            "message": "API 认证失败",
            "suggestion": "请在设置中检查 API Key 是否正确",
        }
    if any(kw in msg for kw in ("timeout", "Timeout", "TimeoutError", "timed out")):
        return {
            "code": "TIMEOUT",
            "message": "请求超时，模型响应过慢",
            "suggestion": "请稍后重试，或尝试切换为响应更快的模型",
        }
    if any(kw in msg for kw in ("rate limit", "429", "quota")):
        return {
            "code": "RATE_LIMIT",
            "message": "API 调用频率已达上限",
            "suggestion": "请稍等片刻后重试",
        }
    if any(
        kw in msg.lower()
        for kw in (
            "does not support image",
            "doesn't support image",
            "image input",
            "vision",
            "multimodal",
            "input image",
            "unsupported image",
            "invalid image",
            "content type image_url",
            "image_url",
        )
    ):
        return {
            "code": "MODEL_NO_VISION",
            "message": "当前模型未接受图片输入，可能不支持视觉能力或当前接入方式不兼容。",
            "suggestion": "系统已实际尝试发送图片。请检查模型本身是否支持读图，以及当前 API/Base URL 是否支持多模态输入。",
        }
    if any(kw in msg for kw in ("Invalid model", "model not found", "404")):
        return {
            "code": "MODEL_NOT_FOUND",
            "message": "指定的模型不存在",
            "suggestion": "请在面板顶部的模型选择器中确认模型名称是否正确",
        }
    if any(kw in msg for kw in ("max iterations", "Agent stopped", "iteration limit")):
        return {
            "code": "MAX_ITERATIONS",
            "message": "模型工具调用次数超限，无法完成任务",
            "suggestion": "请尝试简化问题、减少工具依赖，或切换至其他模型后重试",
        }
    return {
        "code": "INTERNAL_ERROR",
        "message": "处理请求时发生异常",
        "suggestion": "请尝试清除上下文或新建对话后重试",
    }


def _is_max_iterations_output(text: str) -> bool:
    """检测 AgentExecutor 返回的 max iterations 错误字符串"""
    lower = text.lower()
    return (
        "agent stopped due to max iterations" in lower
        or "agent stopped due to iteration limit" in lower
        or (lower.startswith("agent stopped") and "iteration" in lower)
    )


async def _fallback_generate(
    mc: "ModelConfig", user_message: str, tool_outputs: str
) -> str:
    """当 Agent 达到迭代上限时，用单次 LLM 调用基于已有工具结果生成回答"""
    from backend.services.agent_core import get_llm

    try:
        mc = _normalize_model_config(mc)
        resolved_api_key = _resolve_model_api_key(mc)
        llm = get_llm(
            provider=mc.provider,
            model_name=mc.model,
            base_url=mc.base_url,
            api_key=resolved_api_key or None,
            temperature=mc.temperature,
        )
        fallback_prompt = f"""你是一个企业知识库助手。以下是工具已收集到的信息，请基于这些信息直接回答用户问题，用中文作答。

用户问题：{user_message}

工具收集到的信息：
{tool_outputs[:4000]}

请基于以上信息给出完整、清晰的回答："""
        response = await llm.ainvoke(fallback_prompt)
        return response.content.strip()
    except Exception as exc:
        logger.warning("Fallback generate failed: %s", exc)
        return (
            "抱歉，模型处理时间过长，未能生成完整回答。请尝试简化问题或切换模型后重试。"
        )


# ─────────────────────────────────────────────
# Pydantic 请求/响应模型
# ─────────────────────────────────────────────


def _model_config_payload(mc: ModelConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(mc, dict):
        return dict(mc)
    if hasattr(mc, "model_dump"):
        return mc.model_dump()
    return mc.dict()


def _base_model_payload(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


def _normalize_model_config(mc: ModelConfig | dict[str, Any]) -> ModelConfig:
    from backend.services.agent_core import (
        default_base_url_for_connection_type,
        default_model_for_connection_type,
        normalize_connection_type,
    )

    data = _model_config_payload(mc)
    connection_type = normalize_connection_type(
        data.get("connection_type") or data.get("provider"),
        data.get("base_url"),
    )
    data["connection_type"] = connection_type
    data["provider"] = connection_type
    data["base_url"] = str(
        data.get("base_url") or default_base_url_for_connection_type(connection_type)
    ).strip()
    data["model"] = str(
        data.get("model") or default_model_for_connection_type(connection_type)
    ).strip()
    data["api_key"] = str(data.get("api_key") or "").strip()
    data["api_key_ref"] = str(data.get("api_key_ref") or "").strip()
    return ModelConfig(**data)


def _resolve_runtime_model_config(mc: ModelConfig | dict[str, Any]) -> ModelConfig:
    normalized = _normalize_model_config(mc)
    return ModelConfig(
        **{
            **_model_config_payload(normalized),
            "api_key": _resolve_model_api_key(normalized),
        }
    )


def _resolve_report_messages(
    history: Any,
    *,
    answer_group_id: Optional[str] = None,
    panel_id: Optional[str] = None,
) -> list[Any]:
    from langchain_core.messages import AIMessage, HumanMessage

    return resolve_report_messages(
        history,
        answer_group_id=str(answer_group_id or "").strip(),
        panel_id=str(panel_id or "").strip(),
        human_message_factory=lambda content: HumanMessage(content=content),
        ai_message_factory=lambda content: AIMessage(content=content),
    )


# ─────────────────────────────────────────────
# 异步任务状态机
# ─────────────────────────────────────────────


def _update_task_progress(record: TaskRecord, progress: int) -> None:
    return task_runtime._update_task_progress(sys.modules[__name__], record, progress)


async def _drop_suppressed_task(record: TaskRecord) -> bool:
    return await task_runtime._drop_suppressed_task(sys.modules[__name__], record)


async def _create_inline_task_record(
    task_type: str,
    params: dict[str, Any],
    *,
    session_id: Optional[str] = None,
    progress: int = 10,
) -> TaskRecord:
    return await task_runtime._create_inline_task_record(
        sys.modules[__name__],
        task_type,
        params,
        session_id=session_id,
        progress=progress,
    )


async def _set_inline_task_state(
    record: TaskRecord,
    *,
    status: TaskStatus,
    progress: Optional[int] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> TaskRecord:
    return await task_runtime._set_inline_task_state(
        sys.modules[__name__],
        record,
        status=status,
        progress=progress,
        result=result,
        error=error,
    )


def _is_deep_research_task(record: TaskRecord) -> bool:
    return task_runtime._is_deep_research_task(sys.modules[__name__], record)


def _get_deep_research_semaphore() -> asyncio.Semaphore:
    return task_runtime._get_deep_research_semaphore(sys.modules[__name__])


def _get_task_store() -> SQLiteTaskStore:
    return task_runtime._get_task_store(sys.modules[__name__])


def _persist_task_record(record: TaskRecord) -> None:
    return task_runtime._persist_task_record(sys.modules[__name__], record)


def _prune_persisted_tasks() -> None:
    return task_runtime._prune_persisted_tasks(sys.modules[__name__])


def _prune_task_records_locked(now: float | None = None) -> None:
    return task_runtime._prune_task_records_locked(sys.modules[__name__], now)


async def _run_task(record: TaskRecord) -> None:
    return await task_runtime._run_task(sys.modules[__name__], record)


async def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    return await task_runtime.create_task(sys.modules[__name__], request)


async def get_task(task_id: str) -> dict[str, Any]:
    return await task_runtime.get_task(sys.modules[__name__], task_id)


async def list_tasks(limit: int = 20) -> dict[str, Any]:
    return await task_runtime.list_tasks(sys.modules[__name__], limit)


_tasks: dict[str, TaskRecord] = {}
_tasks_lock = asyncio.Lock()
_integrator_scheduler_tick_lock = asyncio.Lock()
_integrator_scheduler_task: asyncio.Task | None = None
_suppressed_task_ids: set[str] = set()
_deep_research_semaphore_lock = threading.Lock()
_deep_research_semaphores: dict[int, asyncio.Semaphore] = {}
_task_store: SQLiteTaskStore | None = None
_task_store_init_lock = threading.Lock()


# ─────────────────────────────────────────────
# 内部工具函数
# ─────────────────────────────────────────────

# 缓存已构建的 agent 实例，key = (provider, model, base_url, api_key, temperature, agent_mode)
_agent_cache: dict[str, Any] = {}
_agent_cache_lock = asyncio.Lock()


async def _clear_agent_cache() -> None:
    async with _agent_cache_lock:
        cleared_count = len(_agent_cache)
        _agent_cache.clear()
    if cleared_count:
        logger.info("Cleared %d cached agent(s)", cleared_count)


def _validate_chat_payload(
    message: str,
    images: list[ImageInput],
    files: list[FileInput],
) -> None:
    _validate_chat_payload_impl(message, images, files)


def _chat_file_suffix(name: str) -> str:
    return _chat_file_suffix_impl(name)


def _decode_data_url(data_url: str, file_name: str) -> bytes:
    return _decode_data_url_impl(data_url, file_name)


def _clip_attachment_preview_text(
    text: str, limit: int = CHAT_ATTACHMENT_PREVIEW_CHARS
) -> str:
    return _clip_attachment_preview_text_impl(text, limit)


def _prepare_chat_files(files: list[FileInput]) -> tuple[list[dict[str, Any]], str]:
    return _prepare_chat_files_impl(
        files,
        config=ChatFileConfig(
            context_end_marker=CHAT_FILE_CONTEXT_END_MARKER,
            context_start_marker=CHAT_FILE_CONTEXT_START_MARKER,
            max_bytes=CHAT_FILE_MAX_BYTES,
            max_chars_per_file=CHAT_FILE_MAX_CHARS_PER_FILE,
            max_count=CHAT_FILE_MAX_COUNT,
            max_total_chars=CHAT_FILE_MAX_TOTAL_CHARS,
            preview_chars=CHAT_ATTACHMENT_PREVIEW_CHARS,
            supported_extensions=frozenset(SUPPORTED_CHAT_FILE_EXTENSIONS),
        ),
        logger=logger,
    )


def _build_message_with_files(message: str, attachment_context: str = "") -> str:
    return _build_message_with_files_impl(message, attachment_context)


def _build_user_input(
    message: str,
    images: list[ImageInput],
    attachment_context: str = "",
) -> Any:
    return _build_user_input_impl(message, images, attachment_context)


def _user_input_has_images(user_input: Any) -> bool:
    return _user_input_has_images_impl(user_input)


def _model_supports_images(provider: str, model_name: str) -> bool:
    return _model_supports_images_impl(provider, model_name)


def _stringify_user_input(user_input: Any) -> str:
    return _stringify_user_input_impl(user_input)


def _request_field_set(model: BaseModel) -> set[str]:
    fields = getattr(model, "model_fields_set", None)
    if fields is None:
        fields = getattr(model, "__fields_set__", set())
    return set(fields or set())


def _clip_text(text: Any, limit: int) -> str:
    return session_summary_runtime._clip_text(sys.modules[__name__], text, limit)


def _summary_llm_enabled() -> bool:
    return session_summary_runtime._summary_llm_enabled(sys.modules[__name__])


def _summary_llm_timeout_seconds() -> float:
    return session_summary_runtime._summary_llm_timeout_seconds(sys.modules[__name__])


def _normalize_llm_text_content(content: Any) -> str:
    return session_summary_runtime._normalize_llm_text_content(
        sys.modules[__name__], content
    )


def _resolve_summary_model_config(
    session_id: str, preferred_model_config: Optional[dict[str, Any]] = None
) -> Optional[ModelConfig]:
    return session_summary_runtime._resolve_summary_model_config(
        sys.modules[__name__], session_id, preferred_model_config
    )


def _build_phase_summary_llm_prompt(
    turns: list[dict[str, Any]], *, total_turns: int
) -> str:
    return session_summary_runtime._build_phase_summary_llm_prompt(
        sys.modules[__name__], turns, total_turns=total_turns
    )


async def _try_llm_phase_summary_content(
    session_id: str,
    turns: list[dict[str, Any]],
    *,
    total_turns: int,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    return await session_summary_runtime._try_llm_phase_summary_content(
        sys.modules[__name__],
        session_id,
        turns,
        total_turns=total_turns,
        preferred_model_config=preferred_model_config,
    )


def _summary_turns(message_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return session_summary_runtime._summary_turns(
        sys.modules[__name__], message_records
    )


def _build_phase_summary_content(
    turns: list[dict[str, Any]], *, total_turns: int
) -> str:
    return session_summary_runtime._build_phase_summary_content(
        sys.modules[__name__], turns, total_turns=total_turns
    )


async def _generate_session_phase_summary_memory(
    session_id: str,
    *,
    trigger: str,
    force: bool = False,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    return await session_summary_runtime._generate_session_phase_summary_memory(
        sys.modules[__name__],
        session_id,
        trigger=trigger,
        force=force,
        preferred_model_config=preferred_model_config,
    )


async def _auto_generate_phase_summary_memory(
    session_id: str,
    *,
    trigger: str,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> None:
    return await session_summary_runtime._auto_generate_phase_summary_memory(
        sys.modules[__name__],
        session_id,
        trigger=trigger,
        preferred_model_config=preferred_model_config,
    )


def _get_attachment_promotion_task(
    attachment_id: str,
    vector_store_path: str,
) -> TaskRecord | None:
    attachment_id = str(attachment_id or "").strip()
    vector_store_path = str(vector_store_path or "").strip()
    if not attachment_id or not vector_store_path:
        return None

    try:
        return _get_task_store().get_attachment_promotion_task(
            attachment_id,
            vector_store_path,
        )
    except Exception:
        logger.exception(
            "Failed to resolve attachment promotion state: %s -> %s",
            attachment_id,
            vector_store_path,
        )
        return None


async def _get_or_build_agent(
    mc: ModelConfig,
    system_prompt: Optional[str] = None,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
    vector_store_path: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
    enabled_mcp_servers: Optional[list[str]] = None,
):
    """获取或构建 Agent（带缓存）"""
    from backend.services.agent_core import build_agent

    mc = _normalize_model_config(mc)
    resolved_api_key = _resolve_model_api_key(mc)
    api_key_hash = _hash_secret(resolved_api_key)
    cache_key = _content_hash(
        {
            "connection_type": mc.connection_type or mc.provider,
            "provider": mc.provider,
            "model": mc.model,
            "base_url": mc.base_url,
            "api_key_hash": api_key_hash,
            "temperature": mc.temperature,
            "agent_mode": mc.agent_mode,
            "web_search_enabled": web_search_enabled,
            "knowledge_base_enabled": knowledge_base_enabled,
            "vector_store_path": str(_resolve_project_subdir(vector_store_path))
            if vector_store_path
            else "",
            "system_prompt": system_prompt or "",
            "dashboard_template": dashboard_template or {},
            "enabled_mcp_servers": normalize_mcp_server_names(enabled_mcp_servers),
        }
    )
    async with _agent_cache_lock:
        if cache_key not in _agent_cache:
            logger.info("Building new agent: %s", cache_key[:12])
            _agent_cache[cache_key] = await build_agent(
                provider=mc.provider,
                model_name=mc.model,
                base_url=mc.base_url,
                api_key=resolved_api_key or None,
                temperature=mc.temperature,
                agent_mode=mc.agent_mode,
                system_prompt=system_prompt,
                web_search_enabled=web_search_enabled,
                knowledge_base_enabled=knowledge_base_enabled,
                vector_store_path=vector_store_path,
                dashboard_template=dashboard_template,
                enabled_mcp_servers=normalize_mcp_server_names(enabled_mcp_servers),
            )
        return _agent_cache[cache_key]


async def _invoke_agent_stream(
    panel_id: str,
    mc: ModelConfig,
    message: Any,
    session_id: str,
    web_search_enabled: bool,
    knowledge_base_enabled: bool,
    system_prompt: Optional[str] = None,
    vector_store_path: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
    enabled_mcp_servers: Optional[list[str]] = None,
    persist_history: bool = True,
    persist_user_history: bool = True,
    persist_ai_history: bool = True,
    replace_ai_history: bool = False,
    exclude_ai_answer_group_id: str = "",
    answer_group_id: str = "",
    raw_user_message: str = "",
    raw_images: Optional[list[dict[str, Any]]] = None,
    raw_files: Optional[list[dict[str, Any]]] = None,
    auto_summary_trigger: bool = False,
) -> AsyncGenerator[str, None]:
    """调用单个 agent，将结果封装为 SSE 事件流"""
    try:
        mc = _normalize_model_config(mc)
        agent = await _get_or_build_agent(
            mc,
            system_prompt=system_prompt,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
            vector_store_path=vector_store_path,
            dashboard_template=dashboard_template,
            enabled_mcp_servers=normalize_mcp_server_names(enabled_mcp_servers),
        )
        answer_parts: list[str] = []
        dashboard_task_record: TaskRecord | None = None

        dashboard_requested = _should_start_dashboard_task(
            raw_user_message or message,
            knowledge_base_enabled=knowledge_base_enabled,
            logger=logger,
        ) and _dashboard_feature_enabled(dashboard_template)
        if dashboard_requested:
            prompt_excerpt = dashboard_prompt_excerpt(raw_user_message)
            dashboard_task_record = await _create_inline_task_record(
                "generate_dashboard",
                {
                    "panel_id": panel_id,
                    "prompt_excerpt": prompt_excerpt,
                },
                session_id=session_id,
                progress=20,
            )
            yield task_created_event(panel_id, dashboard_task_record)

        config_payload = build_agent_config_payload(
            session_id=session_id,
            persist_history=persist_history,
            persist_user_history=persist_user_history,
            persist_ai_history=persist_ai_history,
            replace_ai_history=replace_ai_history,
            exclude_ai_answer_group_id=exclude_ai_answer_group_id,
            panel_id=panel_id,
            model_id=mc.model,
            answer_group_id=answer_group_id,
            raw_user_message=raw_user_message,
            raw_images=raw_images or [],
            raw_files=raw_files or [],
            task_id=dashboard_task_record.task_id if dashboard_task_record else "",
            task_type=dashboard_task_record.task_type if dashboard_task_record else "",
        )

        # 尝试流式输出（LangGraph wrapper 支持 astream_answer）
        if hasattr(agent, "astream_answer"):
            async for item in agent.astream_answer(
                message,
                config=config_payload,
            ):
                event, chunk = stream_agent_item(panel_id, item)
                if chunk:
                    answer_parts.append(chunk)
                yield event
        else:
            # 非流式：一次性返回
            result = await agent.ainvoke(
                {"input": message},
                config=config_payload,
            )
            if _is_max_iterations_output(result.get("output", str(result))):
                logger.warning(
                    "panel_id=%s max iterations reached, attempting fallback", panel_id
                )
            outcome = await resolve_non_stream_agent_result(
                panel_id,
                result,
                mc=mc,
                message=message,
                is_max_iterations_output=_is_max_iterations_output,
                stringify_user_input=_stringify_user_input,
                fallback_generate=_fallback_generate,
            )
            for event in outcome.events:
                yield event
            if outcome.should_stop:
                if dashboard_task_record is not None and outcome.dashboard_error:
                    await fail_dashboard_task(
                        dashboard_task_record,
                        error=outcome.dashboard_error,
                        set_inline_task_state=_set_inline_task_state,
                    )
                return

            answer = outcome.answer
            sources = outcome.sources

            answer_parts.clear()
            answer_parts.append(answer)

            # Emit sources before answer chunks
            if sources:
                yield _panel_event(panel_id, "sources", sources=sources)

            # 将答案分块模拟流式效果（每20字符一块）
            for chunk in answer_chunks(answer, chunk_size=20):
                yield _panel_event(panel_id, "chunk", content=chunk)
                await asyncio.sleep(0.01)

        # 完成信号
        if dashboard_task_record is not None:
            final_answer = "".join(answer_parts)
            await finalize_dashboard_task(
                dashboard_task_record,
                final_answer,
                contains_dashboard_card=_contains_dashboard_card,
                summarize_dashboard_task_result=_summarize_dashboard_task_result,
                summarize_dashboard_task_error=_summarize_dashboard_task_error,
                set_inline_task_state=_set_inline_task_state,
            )

        if auto_summary_trigger and persist_ai_history:
            asyncio.create_task(
                _auto_generate_phase_summary_memory(
                    session_id,
                    trigger=f"chat_stream:{panel_id}",
                    preferred_model_config=_model_config_payload(mc),
                )
            )

        yield _done_event(panel_id)

    except Exception as e:
        logger.exception("Agent invocation failed panel_id=%s", panel_id)
        if "dashboard_task_record" in locals() and dashboard_task_record is not None:
            await fail_dashboard_task(
                dashboard_task_record,
                error=str(e),
                set_inline_task_state=_set_inline_task_state,
            )
        err = _classify_error(e)
        yield _panel_event(
            panel_id,
            "error",
            content=err["message"],
            error_code=err["code"],
            suggestion=err["suggestion"],
        )


async def get_ollama_models(base_url: str = "http://localhost:11434") -> dict[str, Any]:
    """Backward-compatible Ollama model listing used by tests and scripts."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return {"models": [m["name"] for m in models]}
    except httpx.HTTPError as exc:
        logger.warning("Cannot reach Ollama: %s", exc)
        return {"models": [], "error": str(exc)}


async def _run_integrator_scheduler_tick_once(
    *,
    now: float | None = None,
) -> dict[str, Any]:
    return await run_integrator_scheduler_tick(
        _get_app_config_store(),
        tick_lock=_integrator_scheduler_tick_lock,
        now=now,
        tasks=lambda: _tasks,
        tasks_lock=_tasks_lock,
        prune_task_records_locked=_prune_task_records_locked,
        persist_task_record=_persist_task_record,
        prune_persisted_tasks=_prune_persisted_tasks,
        run_task=_run_task,
        enqueue_task=enqueue_task,
        spawn_background_task=asyncio.create_task,
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

    config = _integrator_scheduler_config_from_env()
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


def _register_app_lifecycle_handler(event: str, handler: Any) -> None:
    """Register app lifecycle hooks across FastAPI/Starlette versions."""

    add_event_handler = getattr(app, "add_event_handler", None)
    if callable(add_event_handler):
        add_event_handler(event, handler)
        return

    router = getattr(app, "router", None)
    hook_list = getattr(router, f"on_{event}", None)
    if isinstance(hook_list, list):
        hook_list.append(handler)
        return

    on_event = getattr(app, "on_event", None)
    if callable(on_event):
        on_event(event)(handler)
        return

    raise RuntimeError(f"FastAPI app does not support {event!r} lifecycle hooks")


_register_app_lifecycle_handler("startup", _startup_integrator_scheduler_worker)
_register_app_lifecycle_handler("shutdown", _shutdown_integrator_scheduler_worker)


register_core_routers(sys.modules[__name__])
register_deferred_routers(sys.modules[__name__])
mount_frontend_static(app, backend_file=__file__)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        reload=True,
    )
