"""
FastAPI 后端 API 服务
提供 REST + SSE 端点，包装现有 agent_core / chat_store / doc_pipeline 模块
"""

import asyncio
from dataclasses import dataclass
import hashlib
import importlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import threading
import time
from urllib.parse import quote
import uuid
from typing import Any, AsyncGenerator, Literal, Optional

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

import httpx
from backend.api_config_store import SQLiteAppConfigStore
from backend.api_chat_routes import build_chat_router
from backend.api_content_routes import build_content_router
from backend.api_kb_routes import build_kb_router
from backend.api_operations_routes import build_operations_router
from backend.api_prompt_routes import build_prompt_router
from backend.api_session_routes import build_session_router
from backend.api_security_helpers import (
    auth_capabilities_for_role as _build_auth_capabilities_for_role,
    build_auth_token_catalog_payload as _build_auth_token_catalog_payload,
    build_auth_whoami_payload,
    build_security_status_payload as _build_security_status_payload,
)
from backend.api_security_routes import build_security_router
from artifact_service import (
    SQLiteArtifactStore,
    artifact_export_formats,
    build_deck_artifact,
    build_report_artifact,
    sync_deck_artifact,
)
from agent_mcp_helpers import (
    default_mcp_server_names,
    list_mcp_server_catalog,
    normalize_mcp_server_names,
)
from api_session_helpers import (
    build_answer_group_review_payload as _build_answer_group_review_payload,
    build_session_messages_payload as _build_session_messages_payload,
    collect_session_attachments as _collect_session_attachments,
    find_session_attachment as _find_session_attachment,
    render_shared_deck_html as _render_shared_deck_html,
    render_shared_session_html as _render_shared_session_html,
)
from api_attachment_route_helpers import (
    prepare_attachment_promotion,
    session_attachments_payload,
)
from api_chat_input_helpers import (
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
from api_chat_file_helpers import (
    ChatFileConfig,
    prepare_chat_files as _prepare_chat_files_impl,
)
from api_agent_stream_helpers import (
    dashboard_prompt_excerpt,
    fail_dashboard_task,
    finalize_dashboard_task,
    resolve_non_stream_agent_result,
    stream_agent_item,
    task_created_event,
)
from api_chat_route_helpers import (
    build_parallel_agent_streams,
    build_single_agent_stream,
    prepare_chat_route_runtime,
    sse_streaming_response,
)
from api_workspace_session_helpers import (
    create_session_record,
    reorder_sessions_payload,
    session_update_requested,
    workspaces_payload,
)
from api_document_helpers import (
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
from api_deck_report_helpers import (
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
from api_chat_stream_helpers import (
    answer_chunks,
    build_agent_config_payload,
    done_event as _done_event,
    panel_event as _panel_event,
    stream_parallel_sse,
    stream_single_sse,
)
from api_session_memory_helpers import (
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
from api_session_memory_route_helpers import (
    delete_session_memory_payload,
    pin_session_memory_payload,
    session_memory_payload,
    session_memory_updates,
    summarize_session_memory_payload,
    update_session_memory_payload,
)
from backend.api_security_audit_store import SQLiteSecurityAuditStore
from api_kb_helpers import (
    filter_kb_chunks,
    kb_collect_chunks as _kb_collect_chunks,
    kb_docstore_dict as _kb_docstore_dict,
    kb_rebuild_from_documents as _kb_rebuild_from_documents,
    kb_safe_metadata as _kb_safe_metadata,
)
from api_kb_delete_helpers import delete_kb_directory
from api_kb_management_helpers import (
    kb_health_payload,
    knowledge_bases_payload,
)
from api_kb_chunk_route_helpers import (
    delete_kb_chunk_payload,
    list_kb_chunks_payload,
    update_kb_chunk_payload,
)
from api_share_helpers import (
    build_share_url as _build_share_url,
    decode_share_token as _decode_share_token,
    encode_share_token as _encode_share_token,
    SQLiteShareLinkStore,
)
from api_shared_resource_helpers import open_shared_resource_payload
from api_task_helpers import (
    contains_dashboard_card as _contains_dashboard_card,
    create_inline_task_record,
    prune_task_records,
    set_inline_task_state,
    should_start_dashboard_task as _should_start_dashboard_task,
    summarize_dashboard_task_error as _summarize_dashboard_task_error,
    summarize_dashboard_task_result as _summarize_dashboard_task_result,
)
from api_task_runtime_helpers import (
    attach_current_kb_status,
    enqueue_task,
    list_tasks_payload,
    task_record_payload,
)
from api_task_execution_helpers import (
    persist_web_research_task_placeholder,
    persist_web_research_task_result,
    run_analyze_knowledge_base_task,
    run_generate_deck_task,
    run_generate_report_task,
    run_placeholder_task,
    run_promote_attachment_to_kb_task,
    run_upload_documents_task,
    run_web_research_task,
)
from api_task_store import SQLiteTaskStore, TaskRecord, TaskStatus
from deck_service import (
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
from pydantic import BaseModel, Field

load_dotenv()

_log_format = configure_logging()
logger = logging.getLogger(__name__)
logger.info("日志格式: %s", _log_format)

_app_config_store = SQLiteAppConfigStore()


def _get_app_config_store() -> SQLiteAppConfigStore:
    return _app_config_store


def _stored_config_value(key: str, default: str = "") -> str:
    try:
        return _get_app_config_store().get_value(key, default)
    except Exception:
        logger.exception("Failed to read persisted app config key=%s", key)
        return str(default or "")


def _sync_runtime_secret_from_store(env_name: str, config_key: str) -> str:
    persisted_value = _stored_config_value(config_key, "")
    if persisted_value:
        os.environ[env_name] = persisted_value
        return persisted_value
    return str(os.getenv(env_name) or "").strip()


_CLOUD_MODEL_API_KEY_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,127}$")


def _normalize_cloud_model_api_key_ref(value: Any, *, allow_empty: bool = False) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        if allow_empty:
            return ""
        raise HTTPException(status_code=400, detail="Cloud model API key ref 不能为空。")
    if not _CLOUD_MODEL_API_KEY_REF_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="Cloud model API key ref 格式无效。")
    return normalized


def _cloud_model_api_key_config_key(api_key_ref: str) -> str:
    normalized_ref = _normalize_cloud_model_api_key_ref(api_key_ref)
    return f"cloud_model_api_key:{normalized_ref}"


def _upsert_cloud_model_api_key(api_key_ref: str | None, api_key: str) -> str:
    normalized_api_key = str(api_key or "").strip()
    if not normalized_api_key:
        raise HTTPException(status_code=400, detail="Cloud model API Key 不能为空。")

    normalized_ref = (
        _normalize_cloud_model_api_key_ref(api_key_ref, allow_empty=True)
        if api_key_ref is not None
        else ""
    )
    if not normalized_ref:
        normalized_ref = f"cmk-{uuid.uuid4().hex}"

    _get_app_config_store().set(
        _cloud_model_api_key_config_key(normalized_ref),
        normalized_api_key,
    )
    return normalized_ref


def _delete_cloud_model_api_key(api_key_ref: str) -> bool:
    return _get_app_config_store().delete(_cloud_model_api_key_config_key(api_key_ref))


def _resolve_model_api_key(mc: "ModelConfig | dict[str, Any]") -> str:
    data = _model_config_payload(mc)
    direct_api_key = str(data.get("api_key") or "").strip()
    if direct_api_key:
        return direct_api_key

    api_key_ref = str(data.get("api_key_ref") or "").strip()
    if not api_key_ref:
        return ""

    try:
        return _stored_config_value(_cloud_model_api_key_config_key(api_key_ref), "")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to resolve cloud model API key ref=%s", api_key_ref)
        return ""


async def _validate_tavily_api_key(api_key: str) -> None:
    normalized_key = str(api_key or "").strip()
    if not normalized_key:
        raise HTTPException(status_code=400, detail="Tavily API Key 不能为空。")

    payload = {
        "api_key": normalized_key,
        "query": "OpenAI",
        "max_results": 1,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=502, detail="Tavily API Key 校验超时，请稍后重试。") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Tavily API Key 校验失败，无法连接 Tavily：{exc}",
        ) from exc

    if response.status_code == 401:
        raise HTTPException(status_code=400, detail="Tavily API Key 无效，保存失败。")
    if response.status_code >= 400:
        detail = response.text.strip() or f"HTTP {response.status_code}"
        raise HTTPException(
            status_code=502,
            detail=f"Tavily API Key 校验失败：{detail}",
        )


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
        logger.warning("%s=%r is below minimum=%s; using %s", name, raw, minimum, minimum)
        value = int(minimum)
        source = f"{source}_clamped"

    if maximum is not None and value > maximum:
        logger.warning("%s=%r is above maximum=%s; using %s", name, raw, maximum, maximum)
        value = int(maximum)
        source = f"{source}_clamped"

    return int(value), source

PROJECT_ROOT = BACKEND_DIR.parent
UPLOAD_CHUNK_SIZE = 1024 * 1024
TASK_HISTORY_LIMIT = 200
TASK_HISTORY_TTL_SECONDS = int(os.getenv("TASK_HISTORY_TTL_SECONDS", str(6 * 60 * 60)))
KB_METADATA_TTL_SECONDS = 30
CHAT_FILE_CONTEXT_START_MARKER = "[[CHAT_FILE_CONTEXT_START]]"
CHAT_FILE_CONTEXT_END_MARKER = "[[CHAT_FILE_CONTEXT_END]]"
CHAT_FILE_MAX_COUNT = int(os.getenv("CHAT_FILE_MAX_COUNT", "6"))
CHAT_FILE_MAX_BYTES = int(os.getenv("CHAT_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
CHAT_FILE_MAX_CHARS_PER_FILE = int(
    os.getenv("CHAT_FILE_MAX_CHARS_PER_FILE", "8000")
)
CHAT_FILE_MAX_TOTAL_CHARS = int(os.getenv("CHAT_FILE_MAX_TOTAL_CHARS", "24000"))
CHAT_ATTACHMENT_PREVIEW_CHARS = int(
    os.getenv("CHAT_ATTACHMENT_PREVIEW_CHARS", "4000")
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
SECURITY_AUDIT_MEMORY_WINDOW_LIMIT = 200
SECURITY_AUDIT_HISTORY_LIMIT, SECURITY_AUDIT_HISTORY_LIMIT_SOURCE = _env_int_setting(
    "SECURITY_AUDIT_HISTORY_LIMIT",
    2000,
    minimum=1,
)
REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS, REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE = _env_int_setting(
    "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS",
    60,
    minimum=1,
)
REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS, REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS_SOURCE = _env_int_setting(
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
    if not secret:
        return "no-key"
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _token_fingerprint(token: str) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return "empty"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _token_preview(token: str) -> str:
    normalized = str(token or "").strip()
    if len(normalized) <= 10:
        return normalized
    return f"{normalized[:6]}...{normalized[-4:]}"


def _auth_token_preview(token: str) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return "empty"
    if len(normalized) <= 4:
        return "*" * len(normalized)
    if len(normalized) <= 8:
        return f"{normalized[:2]}...{normalized[-2:]}"
    return f"{normalized[:4]}...{normalized[-2:]}"


def _request_client_ip(request: Request) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client is not None else ""
    return str(host or "").strip()


def _request_user_agent(request: Request) -> str:
    return str(request.headers.get("user-agent") or "").strip()


def _request_is_local(request: Request) -> bool:
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client is not None else ""
    return _is_loopback_host(host)


def _current_admin_api_token() -> str:
    return str(os.getenv("ADMIN_API_TOKEN", "") or "").strip()


def _normalize_auth_role(role: Any, *, default: str = DEFAULT_AUTH_ROLE) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in AUTH_ROLE_RANKS:
        return normalized
    return default


def _role_rank(role: str) -> int:
    return AUTH_ROLE_RANKS.get(_normalize_auth_role(role), 0)


def _sanitize_log_value(value: Any, *, max_length: int = 256) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    if len(text) > max_length:
        return f"{text[: max_length - 3]}..."
    return text


def _auth_capabilities_for_role(role: str) -> list[str]:
    return _build_auth_capabilities_for_role(
        role,
        normalize_auth_role=_normalize_auth_role,
        role_rank=_role_rank,
    )


def _auth_token_is_weak(token: Any) -> bool:
    normalized = str(token or "").strip()
    return len(normalized) < MIN_AUTH_TOKEN_RECOMMENDED_LENGTH


def _auth_token_hygiene_summary(
    auth_records: list[dict[str, str]] | None = None,
) -> dict[str, int | bool]:
    records = auth_records if auth_records is not None else _configured_auth_token_records()
    weak_count = 0
    legacy_count = 0
    for record in records:
        token = record.get("token") or ""
        auth_source = str(record.get("auth_source") or "").strip()
        if _auth_token_is_weak(token):
            weak_count += 1
        if auth_source.startswith("legacy_"):
            legacy_count += 1
    return {
        "weak_count": int(weak_count),
        "legacy_count": int(legacy_count),
        "healthy": weak_count == 0 and legacy_count == 0,
    }


def _configured_auth_token_records() -> list[dict[str, str]]:
    token_records: dict[str, dict[str, str]] = {}

    def _add_token_record(
        token: Any,
        *,
        role: Any,
        user_id: Any = "",
        auth_source: Any = "",
    ) -> None:
        normalized_token = str(token or "").strip()
        if not normalized_token or normalized_token in token_records:
            return
        normalized_role = _normalize_auth_role(role)
        normalized_user_id = _sanitize_log_value(
            user_id or DEFAULT_AUTH_USER_IDS[normalized_role],
            max_length=128,
        )
        token_records[normalized_token] = {
            "token": normalized_token,
            "role": normalized_role,
            "user_id": normalized_user_id,
            "auth_source": _sanitize_log_value(auth_source, max_length=64)
            or "token_catalog",
        }

    raw_catalog = str(os.getenv("APP_AUTH_TOKENS_JSON", "") or "").strip()
    if raw_catalog:
        try:
            parsed_catalog = json.loads(raw_catalog)
        except json.JSONDecodeError:
            logger.warning("Failed to parse APP_AUTH_TOKENS_JSON")
        else:
            catalog_entries: list[Any] = []
            if isinstance(parsed_catalog, list):
                catalog_entries = parsed_catalog
            elif isinstance(parsed_catalog, dict):
                if isinstance(parsed_catalog.get("tokens"), list):
                    catalog_entries = parsed_catalog.get("tokens") or []
                else:
                    catalog_entries = [
                        {"token": token, **value}
                        for token, value in parsed_catalog.items()
                        if isinstance(value, dict)
                    ]
            for entry in catalog_entries:
                if not isinstance(entry, dict):
                    continue
                _add_token_record(
                    entry.get("token") or entry.get("api_token"),
                    role=entry.get("role"),
                    user_id=entry.get("user_id") or entry.get("name"),
                    auth_source=entry.get("auth_source") or "app_auth_tokens_json",
                )

    _add_token_record(
        _current_admin_api_token(),
        role="admin",
        user_id="admin",
        auth_source="legacy_admin_token",
    )
    _add_token_record(
        os.getenv("EDITOR_API_TOKEN"),
        role="editor",
        user_id="editor",
        auth_source="legacy_editor_token",
    )
    _add_token_record(
        os.getenv("VIEWER_API_TOKEN"),
        role="viewer",
        user_id="viewer",
        auth_source="legacy_viewer_token",
    )
    return list(token_records.values())


def _configured_auth_token_map() -> dict[str, dict[str, str]]:
    return {
        record["token"]: {
            "role": record["role"],
            "user_id": record["user_id"],
            "auth_source": record["auth_source"],
        }
        for record in _configured_auth_token_records()
    }


def _extract_request_token(request: Request) -> str:
    header_token = str(request.headers.get("X-API-Token") or "").strip()
    if header_token:
        return header_token
    header_token = str(request.headers.get("X-Admin-Token") or "").strip()
    if header_token:
        return header_token
    authorization = str(request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _extract_admin_token(request: Request) -> str:
    return _extract_request_token(request)


def _request_auth_mode(request: Request) -> str:
    if not ALLOW_REMOTE_CLIENTS:
        return "local_only_mode"
    if _request_is_local(request):
        return "local"
    if str(request.headers.get("X-API-Token") or "").strip():
        return "header"
    if str(request.headers.get("X-Admin-Token") or "").strip():
        return "header"
    authorization = str(request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return "bearer"
    return "missing"


def _admin_auth_mode(request: Request) -> str:
    return _request_auth_mode(request)


def _resolve_request_auth(request: Request) -> dict[str, Any]:
    cached = getattr(request.state, "resolved_auth", None)
    if isinstance(cached, dict):
        return cached

    is_local_request = _request_is_local(request)
    bypass_enabled = (not ALLOW_REMOTE_CLIENTS) or is_local_request
    auth_mode = _request_auth_mode(request)
    token_present = False
    token_valid = False
    trusted_user_id = ""
    trusted_role = ""
    trusted_source = ""

    if bypass_enabled:
        trusted_user_id = (
            _sanitize_log_value(request.headers.get("X-User-Id"), max_length=128)
            or "local"
        )
        trusted_role = "admin"
        trusted_source = "local_bypass" if is_local_request else "local_only_mode"
        token_valid = True
    else:
        request_token = _extract_request_token(request)
        token_present = bool(request_token)
        auth_record = _configured_auth_token_map().get(request_token)
        if auth_record is not None:
            trusted_user_id = str(auth_record.get("user_id") or "").strip()
            trusted_role = _normalize_auth_role(auth_record.get("role"))
            trusted_source = str(auth_record.get("auth_source") or "").strip()
            token_valid = True

    resolved_auth = {
        "is_local": bool(is_local_request),
        "bypass_enabled": bool(bypass_enabled),
        "auth_mode": auth_mode,
        "token_present": token_present,
        "token_valid": token_valid,
        "user_id": trusted_user_id,
        "role": trusted_role,
        "auth_source": trusted_source,
    }
    request.state.resolved_auth = resolved_auth
    return resolved_auth


def _request_user_id(request: Request) -> str:
    return str(_resolve_request_auth(request).get("user_id") or "").strip()


def _request_user_role(request: Request) -> str:
    return str(_resolve_request_auth(request).get("role") or "").strip()


def _request_auth_source(request: Request) -> str:
    return str(_resolve_request_auth(request).get("auth_source") or "").strip()


def _sanitize_request_path(path: str) -> str:
    normalized = str(path or "").strip() or "/"
    if normalized.startswith("/api/share-links/"):
        return "/api/share-links/<token>"
    if normalized.startswith("/shared/"):
        return "/shared/<token>"
    return normalized


def _remote_management_rate_limit_applies(request: Request) -> bool:
    if not REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED:
        return False
    if not ALLOW_REMOTE_CLIENTS or _request_is_local(request):
        return False
    if str(request.method or "").strip().upper() == "OPTIONS":
        return False
    path = _sanitize_request_path(request.url.path)
    return any(path.startswith(prefix) for prefix in _REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES)


def _remote_management_rate_limit_principal(request: Request) -> str:
    token = _extract_request_token(request)
    if token:
        return f"token:{_token_fingerprint(token)}"
    ip = _request_client_ip(request) or "unknown"
    return f"ip:{ip}"


def _ceil_seconds(seconds: float) -> int:
    normalized = float(seconds or 0.0)
    if normalized <= 0:
        return 0
    truncated = int(normalized)
    if float(truncated) < normalized:
        truncated += 1
    return max(1, truncated)


def _consume_remote_management_rate_limit(request: Request) -> dict[str, Any] | None:
    if not _remote_management_rate_limit_applies(request):
        return None

    now = time.time()
    window_seconds = int(REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS)
    max_requests = int(REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS)
    principal = _remote_management_rate_limit_principal(request)
    path = _sanitize_request_path(request.url.path)

    with _remote_management_rate_limit_lock:
        expired_cutoff = now - float(window_seconds)
        stale_principals = [
            key
            for key, value in _remote_management_rate_limits.items()
            if float(value.get("window_started_at", 0.0) or 0.0) <= expired_cutoff
        ]
        for key in stale_principals:
            _remote_management_rate_limits.pop(key, None)

        state = _remote_management_rate_limits.get(principal)
        if state is None or (now - float(state.get("window_started_at", 0.0) or 0.0)) >= float(window_seconds):
            state = {
                "window_started_at": float(now),
                "count": 0.0,
            }

        current_count = int(state.get("count", 0.0) or 0)
        allowed = current_count < max_requests
        if allowed:
            current_count += 1
            state["count"] = float(current_count)
            _remote_management_rate_limits[principal] = state
        else:
            _remote_management_rate_limits[principal] = state

        remaining = max(0, max_requests - current_count)
        reset_after_seconds = max(
            0.0,
            float(window_seconds) - (now - float(state.get("window_started_at", now) or now)),
        )
        retry_after = _ceil_seconds(reset_after_seconds) if not allowed else 0

    return {
        "allowed": bool(allowed),
        "principal": principal,
        "path": path,
        "limit": max_requests,
        "remaining": remaining,
        "window_seconds": window_seconds,
        "retry_after": retry_after,
        "reset_after_seconds": _ceil_seconds(reset_after_seconds),
    }


def _current_share_link_secret() -> str:
    return str(os.getenv("SHARE_LINK_SECRET", SHARE_LINK_SECRET) or "").strip()


def _share_link_secret_is_weak() -> bool:
    secret = _current_share_link_secret()
    return (
        not secret
        or secret == DEFAULT_SHARE_LINK_SECRET
        or len(secret) < MIN_SHARE_LINK_SECRET_LENGTH
    )


def _require_remote_role(request: Request, *, minimum_role: str = "admin") -> dict[str, Any]:
    auth = _resolve_request_auth(request)
    if auth["bypass_enabled"]:
        return auth

    configured_records = _configured_auth_token_records()
    if not configured_records:
        _audit_security_event(
            "remote_auth_guard",
            request,
            result="blocked",
            details=f"reason=auth_not_configured required_role={minimum_role}",
        )
        raise HTTPException(
            status_code=503,
            detail="Remote access is disabled until API tokens are configured.",
        )

    if not auth["token_valid"]:
        reason = "missing_token" if not auth["token_present"] else "invalid_token"
        _audit_security_event(
            "remote_auth_guard",
            request,
            result="rejected",
            details=f"reason={reason} required_role={minimum_role}",
        )
        raise HTTPException(status_code=403, detail="Missing or invalid API token.")

    actual_role = str(auth["role"] or "").strip()
    if _role_rank(actual_role) < _role_rank(minimum_role):
        _audit_security_event(
            "remote_auth_guard",
            request,
            result="rejected",
            details=(
                f"reason=insufficient_role required_role={minimum_role} "
                f"actual_role={actual_role or '<none>'}"
            ),
        )
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient role: {minimum_role} required.",
        )
    return auth


def _require_remote_viewer(request: Request) -> dict[str, Any]:
    return _require_remote_role(request, minimum_role="viewer")


def _require_remote_editor(request: Request) -> dict[str, Any]:
    return _require_remote_role(request, minimum_role="editor")


def _require_remote_admin(request: Request) -> dict[str, Any]:
    return _require_remote_role(request, minimum_role="admin")


def _require_remote_share_secret(request: Request) -> None:
    if not ALLOW_REMOTE_CLIENTS or _request_is_local(request):
        return
    if _share_link_secret_is_weak():
        _audit_security_event(
            "remote_share_guard",
            request,
            result="blocked",
            details="reason=weak_share_link_secret",
        )
        raise HTTPException(
            status_code=503,
            detail="Remote sharing is disabled until SHARE_LINK_SECRET is strong enough.",
        )


def _content_hash(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        payload = value
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audit_security_event(
    action: str,
    request: Request,
    *,
    result: str = "ok",
    details: str = "",
) -> None:
    request_id = getattr(request.state, "request_id", "")
    event = {
        "timestamp": time.time(),
        "request_id": str(request_id or "").strip(),
        "action": _sanitize_log_value(action, max_length=128),
        "result": _sanitize_log_value(result, max_length=32),
        "ip": _sanitize_log_value(_request_client_ip(request), max_length=64),
        "is_local": bool(_request_is_local(request)),
        "auth_mode": _sanitize_log_value(_request_auth_mode(request), max_length=32),
        "auth_source": _sanitize_log_value(_request_auth_source(request), max_length=64),
        "user_id": _sanitize_log_value(_request_user_id(request), max_length=128),
        "user_role": _sanitize_log_value(_request_user_role(request), max_length=64),
        "details": _sanitize_log_value(details, max_length=512),
    }
    with _security_audit_events_lock:
        _security_audit_events.append(event)
        del _security_audit_events[:-SECURITY_AUDIT_MEMORY_WINDOW_LIMIT]
    _persist_security_audit_event(event)
    logger.info(
        (
            "security_event action=%s result=%s request_id=%s ip=%s local=%s "
            "auth=%s auth_source=%s user_id=%s user_role=%s details=%s"
        ),
        event["action"],
        event["result"],
        event["request_id"],
        event["ip"],
        event["is_local"],
        event["auth_mode"],
        event["auth_source"],
        event["user_id"],
        event["user_role"],
        event["details"],
    )


def _share_link_audit_payload(record: Any, *, now: Optional[float] = None) -> dict[str, Any]:
    current_time = time.time() if now is None else float(now)
    revoked_at = getattr(record, "revoked_at", None)
    expires_at = float(getattr(record, "expires_at", 0) or 0)
    share_token = str(getattr(record, "share_token", "") or "").strip()
    return {
        "resource_type": str(getattr(record, "resource_type", "") or "").strip(),
        "resource_id": str(getattr(record, "resource_id", "") or "").strip(),
        "created_at": float(getattr(record, "created_at", 0) or 0),
        "expires_at": expires_at,
        "revoked_at": float(revoked_at) if revoked_at is not None else None,
        "is_active": revoked_at is None and expires_at > current_time,
        "created_by_ip": str(getattr(record, "created_by_ip", "") or "").strip(),
        "created_user_agent": str(getattr(record, "created_user_agent", "") or "").strip(),
        "access_count": int(getattr(record, "access_count", 0) or 0),
        "last_accessed_at": (
            float(getattr(record, "last_accessed_at", 0))
            if getattr(record, "last_accessed_at", None) is not None
            else None
        ),
        "last_accessed_ip": str(getattr(record, "last_accessed_ip", "") or "").strip(),
        "last_accessed_user_agent": str(
            getattr(record, "last_accessed_user_agent", "") or ""
        ).strip(),
        "share_token_preview": _token_preview(share_token),
        "share_token_fingerprint": _token_fingerprint(share_token),
    }


def _security_status_payload() -> dict[str, Any]:
    cors_origins, cors_allow_credentials = _cors_settings()
    return _build_security_status_payload(
        allow_remote_clients=ALLOW_REMOTE_CLIENTS,
        share_link_ttl_seconds=SHARE_LINK_TTL_SECONDS,
        remote_management_rate_limit_enabled=REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED,
        remote_management_rate_limit_window_seconds=REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS,
        remote_management_rate_limit_window_seconds_source=REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE,
        remote_management_rate_limit_max_requests=REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS,
        remote_management_rate_limit_max_requests_source=REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS_SOURCE,
        security_audit_history_limit=SECURITY_AUDIT_HISTORY_LIMIT,
        security_audit_history_limit_source=SECURITY_AUDIT_HISTORY_LIMIT_SOURCE,
        security_audit_memory_window_limit=SECURITY_AUDIT_MEMORY_WINDOW_LIMIT,
        chat_file_limits={
            "max_count": int(CHAT_FILE_MAX_COUNT),
            "max_bytes": int(CHAT_FILE_MAX_BYTES),
            "max_chars_per_file": int(CHAT_FILE_MAX_CHARS_PER_FILE),
            "max_total_chars": int(CHAT_FILE_MAX_TOTAL_CHARS),
            "preview_chars": int(CHAT_ATTACHMENT_PREVIEW_CHARS),
        },
        document_upload_limits={
            "max_count": int(DOCUMENT_UPLOAD_MAX_COUNT),
            "max_file_bytes": int(DOCUMENT_UPLOAD_MAX_FILE_BYTES),
            "max_total_bytes": int(DOCUMENT_UPLOAD_MAX_TOTAL_BYTES),
        },
        cors_allowed_origins=cors_origins,
        cors_allow_credentials=cors_allow_credentials,
        configured_auth_token_records=_configured_auth_token_records,
        auth_token_hygiene_summary=_auth_token_hygiene_summary,
        role_rank=_role_rank,
        share_link_secret_is_weak=_share_link_secret_is_weak,
        read_security_audit_event_count=lambda: _get_security_audit_store().count_events(),
        logger=logger,
    )


def _auth_token_catalog_payload() -> dict[str, Any]:
    return _build_auth_token_catalog_payload(
        default_role=DEFAULT_AUTH_ROLE,
        configured_auth_token_records=_configured_auth_token_records,
        auth_token_hygiene_summary=_auth_token_hygiene_summary,
        auth_token_preview=_auth_token_preview,
        token_fingerprint=_token_fingerprint,
        auth_token_is_weak=_auth_token_is_weak,
        role_rank=_role_rank,
    )


def _runtime_status_class(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    if 300 <= status_code < 400:
        return "3xx"
    if 400 <= status_code < 500:
        return "4xx"
    if 500 <= status_code < 600:
        return "5xx"
    return "other"


def _record_runtime_request(*, status_code: int, timestamp: float | None = None) -> None:
    recorded_at = time.time() if timestamp is None else float(timestamp)
    status_class = _runtime_status_class(int(status_code))
    with _runtime_metrics_lock:
        _runtime_metrics["total_requests"] += 1
        _runtime_metrics["by_status_class"][status_class] = (
            int(_runtime_metrics["by_status_class"].get(status_class, 0)) + 1
        )
        _runtime_metrics["last_request_at"] = recorded_at


def _record_runtime_error(
    *,
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    timestamp: float | None = None,
) -> None:
    recorded_at = time.time() if timestamp is None else float(timestamp)
    error_entry = {
        "timestamp": recorded_at,
        "request_id": str(getattr(request.state, "request_id", "") or "").strip(),
        "path": _sanitize_request_path(request.url.path),
        "method": str(request.method or "").strip().upper(),
        "status_code": int(status_code),
        "error_code": _sanitize_log_value(error_code, max_length=64),
        "message": _sanitize_log_value(message, max_length=240),
    }
    with _runtime_metrics_lock:
        _runtime_metrics["total_errors"] += 1
        _runtime_metrics["last_error_at"] = recorded_at
        recent_errors = list(_runtime_metrics.get("recent_errors") or [])
        recent_errors.append(error_entry)
        _runtime_metrics["recent_errors"] = recent_errors[-RUNTIME_RECENT_ERROR_LIMIT:]


def _runtime_request_metrics_payload() -> dict[str, Any]:
    with _runtime_metrics_lock:
        by_status_class = {
            str(key): int(value or 0)
            for key, value in dict(_runtime_metrics["by_status_class"]).items()
        }
        recent_errors = [dict(item) for item in list(_runtime_metrics["recent_errors"])]
        return {
            "total_requests": int(_runtime_metrics["total_requests"]),
            "total_errors": int(_runtime_metrics["total_errors"]),
            "by_status_class": by_status_class,
            "last_request_at": _runtime_metrics["last_request_at"],
            "last_error_at": _runtime_metrics["last_error_at"],
            "recent_errors": recent_errors,
        }


def _security_audit_events_payload(
    *,
    limit: int = 50,
    action: str = "",
    result: str = "",
) -> dict[str, Any]:
    max_limit = int(SECURITY_AUDIT_HISTORY_LIMIT)
    try:
        max_limit = max(max_limit, int(_get_security_audit_store().history_limit))
    except Exception:
        logger.exception("Failed to read security audit history limit")
    normalized_limit = max(1, min(int(limit or 50), max_limit))
    normalized_action = str(action or "").strip().lower()
    normalized_result = str(result or "").strip().lower()
    try:
        stored_events = _get_security_audit_store().list_events(
            limit=normalized_limit,
            action=normalized_action,
            result=normalized_result,
        )
    except Exception:
        logger.exception("Failed to load persisted security audit events")
        stored_events = []
    if stored_events:
        events = [
            {
                "timestamp": record.timestamp,
                "request_id": record.request_id,
                "action": record.action,
                "result": record.result,
                "ip": record.ip,
                "is_local": record.is_local,
                "auth_mode": record.auth_mode,
                "auth_source": record.auth_source,
                "user_id": record.user_id,
                "user_role": record.user_role,
                "details": record.details,
            }
            for record in stored_events
        ]
    else:
        with _security_audit_events_lock:
            events = [dict(item) for item in _security_audit_events]
        if normalized_action:
            events = [
                item
                for item in events
                if str(item.get("action") or "").strip().lower() == normalized_action
            ]
        if normalized_result:
            events = [
                item
                for item in events
                if str(item.get("result") or "").strip().lower() == normalized_result
            ]
        events = events[-normalized_limit:]
    return {
        "events": events,
        "total": len(events),
        "limit": normalized_limit,
    }


def _get_security_audit_store() -> SQLiteSecurityAuditStore:
    global _security_audit_store
    if _security_audit_store is None:
        with _security_audit_store_init_lock:
            if _security_audit_store is None:
                _security_audit_store = SQLiteSecurityAuditStore(
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


def _cleanup_security_audit_events(*, keep_latest: int = 0) -> dict[str, Any]:
    normalized_keep_latest = max(
        0,
        min(int(keep_latest or 0), int(SECURITY_AUDIT_HISTORY_LIMIT)),
    )
    deleted_count = _get_security_audit_store().trim_to_latest(normalized_keep_latest)
    remaining_count = _get_security_audit_store().count_events()
    with _security_audit_events_lock:
        memory_before_count = len(_security_audit_events)
        if normalized_keep_latest <= 0:
            _security_audit_events.clear()
        else:
            _security_audit_events[:] = _security_audit_events[-normalized_keep_latest:]
        memory_remaining_count = len(_security_audit_events)
    return {
        "keep_latest": normalized_keep_latest,
        "deleted_count": int(deleted_count),
        "remaining_count": int(remaining_count),
        "memory_deleted_count": int(max(0, memory_before_count - memory_remaining_count)),
        "memory_remaining_count": int(memory_remaining_count),
        "history_limit": int(SECURITY_AUDIT_HISTORY_LIMIT),
    }


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
    return {
        "in_memory_total": len(records),
        "pending": counts[TaskStatus.PENDING.value],
        "running": counts[TaskStatus.RUNNING.value],
        "completed": counts[TaskStatus.COMPLETED.value],
        "failed": counts[TaskStatus.FAILED.value],
        "latest_task_updated_at": latest_task_updated_at,
    }


async def _runtime_operations_payload() -> dict[str, Any]:
    metrics = _runtime_request_metrics_payload()
    return {
        "started_at": _runtime_started_at,
        "uptime_seconds": round(max(0.0, time.time() - _runtime_started_at), 3),
        "request_metrics": {
            "total_requests": metrics["total_requests"],
            "total_errors": metrics["total_errors"],
            "by_status_class": metrics["by_status_class"],
            "last_request_at": metrics["last_request_at"],
            "last_error_at": metrics["last_error_at"],
        },
        "recent_errors": metrics["recent_errors"],
        "task_summary": await _runtime_task_summary_payload(),
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
        dict(dashboard_template_raw)
        if isinstance(dashboard_template_raw, dict)
        else {}
    )

    return system_prompt_content, vector_store_path, dashboard_template


def _dashboard_feature_enabled(dashboard_template: Optional[dict[str, Any]]) -> bool:
    if not isinstance(dashboard_template, dict):
        return True
    return dashboard_template.get("enabled") is not False


def _effective_vector_store_path(candidate: Optional[str] = None) -> str:
    raw = str(candidate or "").strip()
    if not raw:
        raw = _active_vector_store_id() or os.getenv("VECTOR_STORE_PATH", "./vector_store")
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

    ascii_fallback = re.sub(r'[^A-Za-z0-9._-]+', "_", raw_filename).strip("._")
    if not ascii_fallback:
        ascii_fallback = "download"
    encoded = quote(raw_filename, safe="")
    return f"attachment; filename={ascii_fallback}; filename*=UTF-8''{encoded}"


ALLOW_REMOTE_CLIENTS = _env_flag("ALLOW_REMOTE_CLIENTS", False)
_cors_origins, _cors_allow_credentials = _cors_settings()
_REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES = (
    "/api/security/",
    "/api/auth/",
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
_deck_store = SQLiteDeckStore()
_artifact_store = SQLiteArtifactStore()
_share_link_store = SQLiteShareLinkStore()
_runtime_started_at = time.time()
_security_audit_events_lock = threading.Lock()
_runtime_metrics_lock = threading.Lock()
_remote_management_rate_limit_lock = threading.Lock()
_security_audit_events: list[dict[str, Any]] = []
_security_audit_store: SQLiteSecurityAuditStore | None = None
_security_audit_store_init_lock = threading.Lock()
_remote_management_rate_limits: dict[str, dict[str, float]] = {}


def _new_runtime_metrics_state() -> dict[str, Any]:
    return {
        "total_requests": 0,
        "total_errors": 0,
        "by_status_class": {
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
            "other": 0,
        },
        "last_request_at": None,
        "last_error_at": None,
        "recent_errors": [],
    }


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


def _create_report_artifact(
    *,
    session_id: str,
    messages: list[Any],
    answer_group_id: str = "",
    panel_id: str = "",
) -> tuple[Any, str, str]:
    qa_pairs = ensure_deckable_chat(messages)
    title = build_chat_report_title(messages)
    markdown = build_report_markdown(messages, title)
    artifact = build_report_artifact(
        session_id=session_id,
        title=title,
        markdown=markdown,
        qa_pairs=qa_pairs,
        answer_group_id=answer_group_id,
        panel_id=panel_id,
    )
    _artifact_store.save(artifact)
    return artifact, title, markdown


def _create_deck_artifact(deck: Any) -> Any:
    artifact = build_deck_artifact(deck)
    _artifact_store.save(artifact)
    return artifact


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
    _record_runtime_request(status_code=int(response.status_code), timestamp=time.time())
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
        if int(response.status_code) == 429 and int(rate_limit_payload["retry_after"]) > 0:
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
    logger.exception("Unhandled exception request_id=%s on %s", request_id, request.url.path)
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
    from agent_core import get_llm

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


class ModelConfig(BaseModel):
    panel_id: str
    connection_type: Optional[str] = None
    provider: str = "ollama"
    model: str = "qwen3.5-2B:latest"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    api_key_ref: str = ""
    temperature: float = 0.3
    agent_mode: str = "auto"


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
    from agent_core import (
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
    data["base_url"] = (
        str(data.get("base_url") or default_base_url_for_connection_type(connection_type)).strip()
    )
    data["model"] = (
        str(data.get("model") or default_model_for_connection_type(connection_type)).strip()
    )
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


class ImageInput(BaseModel):
    name: str
    media_type: str
    data_url: str


class FileInput(BaseModel):
    name: str
    media_type: str
    data_url: str
    size_bytes: int = 0
    extracted_text: str = ""


class ChatRequest(BaseModel):
    session_id: str
    message: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)
    models: list[ModelConfig]
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True
    enabled_mcp_servers: list[str] = Field(default_factory=list)
    answer_group_id: Optional[str] = None


class SingleChatRequest(BaseModel):
    session_id: str
    message: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)
    panel_config: ModelConfig
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True
    enabled_mcp_servers: list[str] = Field(default_factory=list)
    answer_group_id: Optional[str] = None
    persist_user_history: bool = True
    persist_ai_history: bool = True
    replace_ai_history: bool = False
    exclude_ai_answer_group_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: str = ""
    workspace_id: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_favorite: Optional[bool] = None
    is_pinned: Optional[bool] = None
    tags: Optional[list[str]] = None
    workspace_id: Optional[str] = None


class ReorderSessionsRequest(BaseModel):
    session_ids: list[str]
    workspace_id: Optional[str] = None


class CreateBookmarkRequest(BaseModel):
    session_id: str
    role: str
    message_id: Optional[int] = None
    panel_id: str = ""
    answer_group_id: str = ""
    content: str = ""
    model_id: str = ""
    session_title: str = ""


class ShareLinkResponse(BaseModel):
    resource_type: str
    resource_id: str
    share_token: str
    share_url: str
    expires_at: float


class RevokeShareLinkResponse(BaseModel):
    ok: bool


class ShareLinkAuditRecord(BaseModel):
    resource_type: str
    resource_id: str
    created_at: float
    expires_at: float
    revoked_at: Optional[float] = None
    is_active: bool
    created_by_ip: str = ""
    created_user_agent: str = ""
    access_count: int = 0
    last_accessed_at: Optional[float] = None
    last_accessed_ip: str = ""
    last_accessed_user_agent: str = ""
    share_token_preview: str
    share_token_fingerprint: str


class ShareLinkAuditListResponse(BaseModel):
    share_links: list[ShareLinkAuditRecord]
    total: int
    active_count: int


class SecurityStatusResponse(BaseModel):
    allow_remote_clients: bool
    local_only_mode: bool
    remote_auth_ready: bool
    admin_token_configured: bool
    remote_admin_ready: bool
    auth_token_count: int
    configured_roles: list[str]
    auth_token_hygiene_healthy: bool
    weak_auth_token_count: int
    legacy_auth_token_count: int
    share_link_secret_healthy: bool
    remote_share_ready: bool
    remote_management_rate_limit_enabled: bool
    remote_management_rate_limit_window_seconds: int
    remote_management_rate_limit_window_seconds_source: str
    remote_management_rate_limit_max_requests: int
    remote_management_rate_limit_max_requests_source: str
    share_link_ttl_seconds: int
    share_link_ttl_hours: float
    cors_allow_credentials: bool
    cors_allowed_origins: list[str]
    request_id_header: str
    process_time_header: str
    security_audit_storage: str
    security_audit_history_limit: int
    security_audit_history_limit_source: str
    security_audit_persisted_count: int
    security_audit_memory_window_limit: int
    chat_file_limits: dict[str, int]
    document_upload_limits: dict[str, int]


class AuthWhoAmIResponse(BaseModel):
    user_id: str
    role: str
    auth_mode: str
    auth_source: str
    is_local: bool
    capabilities: list[str]


class AuthTokenCatalogRecord(BaseModel):
    user_id: str
    role: str
    auth_source: str
    token_preview: str
    token_fingerprint: str
    is_legacy: bool
    is_weak: bool


class AuthTokenCatalogResponse(BaseModel):
    tokens: list[AuthTokenCatalogRecord]
    total: int
    configured_roles: list[str]
    healthy: bool
    weak_count: int
    legacy_count: int


class SecurityAuditEventRecord(BaseModel):
    timestamp: float
    request_id: str
    action: str
    result: str
    ip: str
    is_local: bool
    auth_mode: str
    auth_source: str
    user_id: str
    user_role: str
    details: str


class SecurityAuditEventListResponse(BaseModel):
    events: list[SecurityAuditEventRecord]
    total: int
    limit: int


class SecurityAuditCleanupResponse(BaseModel):
    deleted_count: int
    remaining_count: int
    memory_deleted_count: int
    memory_remaining_count: int
    keep_latest: int
    history_limit: int
    includes_cleanup_event: bool


app.include_router(
    build_security_router(
        security_status_response_model=SecurityStatusResponse,
        auth_whoami_response_model=AuthWhoAmIResponse,
        auth_token_catalog_response_model=AuthTokenCatalogResponse,
        security_audit_event_list_response_model=SecurityAuditEventListResponse,
        security_audit_cleanup_response_model=SecurityAuditCleanupResponse,
        require_remote_viewer=_require_remote_viewer,
        require_remote_admin=_require_remote_admin,
        security_status_payload=lambda: _security_status_payload(),
        auth_whoami_payload=lambda auth: build_auth_whoami_payload(
            auth,
            default_role="admin",
            normalize_auth_role=_normalize_auth_role,
            role_rank=_role_rank,
        ),
        auth_token_catalog_payload=lambda: _auth_token_catalog_payload(),
        security_audit_events_payload=lambda **kwargs: _security_audit_events_payload(**kwargs),
        cleanup_security_audit_events=lambda **kwargs: _cleanup_security_audit_events(**kwargs),
        audit_security_event=_audit_security_event,
        get_security_audit_store_count=lambda: _get_security_audit_store().count_events(),
        get_memory_security_audit_event_count=lambda: len(_security_audit_events),
        logger=logger,
    )
)


class RuntimeRequestMetricsResponse(BaseModel):
    total_requests: int
    total_errors: int
    by_status_class: dict[str, int]
    last_request_at: float | None = None
    last_error_at: float | None = None


class RuntimeRecentErrorResponse(BaseModel):
    timestamp: float
    request_id: str
    path: str
    method: str
    status_code: int
    error_code: str
    message: str


class RuntimeTaskSummaryResponse(BaseModel):
    in_memory_total: int
    pending: int
    running: int
    completed: int
    failed: int
    latest_task_updated_at: float | None = None


class RuntimeOperationsResponse(BaseModel):
    started_at: float
    uptime_seconds: float
    request_metrics: RuntimeRequestMetricsResponse
    recent_errors: list[RuntimeRecentErrorResponse]
    task_summary: RuntimeTaskSummaryResponse
    security: dict[str, Any]


app.include_router(
    build_operations_router(
        runtime_operations_response_model=RuntimeOperationsResponse,
        require_remote_viewer=_require_remote_viewer,
        require_remote_admin=_require_remote_admin,
        runtime_request_metrics_payload=lambda: _runtime_request_metrics_payload(),
        runtime_task_summary_payload=lambda: _runtime_task_summary_payload(),
        runtime_operations_payload=lambda: _runtime_operations_payload(),
        get_runtime_started_at=lambda: _runtime_started_at,
        sync_runtime_secret_from_store=lambda env_name, config_key: _sync_runtime_secret_from_store(
            env_name,
            config_key,
        ),
        validate_tavily_api_key=lambda api_key: _validate_tavily_api_key(api_key),
        get_app_config_store=lambda: _get_app_config_store(),
        upsert_cloud_model_api_key=lambda api_key_ref, api_key: _upsert_cloud_model_api_key(
            api_key_ref,
            api_key,
        ),
        delete_cloud_model_api_key=lambda api_key_ref: _delete_cloud_model_api_key(api_key_ref),
        audit_security_event=_audit_security_event,
    )
)


app.include_router(
    build_prompt_router(
        require_remote_viewer=_require_remote_viewer,
        require_remote_editor=_require_remote_editor,
        list_system_prompts=lambda: importlib.import_module("chat_store").get_all_system_prompts(),
        create_system_prompt=lambda *args, **kwargs: importlib.import_module(
            "chat_store"
        ).create_system_prompt(*args, **kwargs),
        update_system_prompt=lambda *args, **kwargs: importlib.import_module(
            "chat_store"
        ).update_system_prompt(*args, **kwargs),
        delete_system_prompt=lambda prompt_id: importlib.import_module(
            "chat_store"
        ).delete_system_prompt(prompt_id),
        activate_system_prompt=lambda prompt_id: importlib.import_module(
            "chat_store"
        ).activate_system_prompt(prompt_id),
        clear_agent_cache=lambda: _clear_agent_cache(),
        build_doc_pipeline=lambda vector_store_path: importlib.import_module(
            "doc_pipeline"
        ).DocPipeline(vector_store_path=vector_store_path),
        audit_security_event=_audit_security_event,
        logger=logger,
    )
)

app.include_router(
    build_kb_router(
        backend_dir=str(BACKEND_DIR),
        require_remote_viewer=_require_remote_viewer,
        require_remote_editor=_require_remote_editor,
        require_remote_admin=_require_remote_admin,
        effective_vector_store_path=lambda path: _effective_vector_store_path(path),
        resolve_project_subdir=lambda candidate: _resolve_project_subdir(candidate),
        resolve_deletable_knowledge_base=lambda candidate: _resolve_deletable_knowledge_base(
            candidate
        ),
        active_vector_store_id=lambda: _active_vector_store_id(),
        faiss_safe_store_path=lambda target_path: _faiss_safe_store_path(target_path),
        build_doc_pipeline=lambda vector_store_path: importlib.import_module(
            "doc_pipeline"
        ).DocPipeline(vector_store_path=vector_store_path),
        list_kb_chunks_payload=lambda **kwargs: list_kb_chunks_payload(**kwargs),
        update_kb_chunk_payload=lambda **kwargs: update_kb_chunk_payload(**kwargs),
        delete_kb_chunk_payload=lambda **kwargs: delete_kb_chunk_payload(**kwargs),
        knowledge_bases_payload=lambda **kwargs: knowledge_bases_payload(**kwargs),
        kb_health_payload=lambda *args, **kwargs: kb_health_payload(*args, **kwargs),
        retrieval_test_payload=lambda *args, **kwargs: retrieval_test_payload(*args, **kwargs),
        kb_collect_chunks=lambda *args, **kwargs: _kb_collect_chunks(*args, **kwargs),
        filter_kb_chunks=lambda *args, **kwargs: filter_kb_chunks(*args, **kwargs),
        kb_docstore_dict=lambda *args, **kwargs: _kb_docstore_dict(*args, **kwargs),
        kb_safe_metadata=lambda *args, **kwargs: _kb_safe_metadata(*args, **kwargs),
        kb_rebuild_from_documents=lambda *args, **kwargs: _kb_rebuild_from_documents(
            *args,
            **kwargs,
        ),
        doc_factory=lambda page_content, metadata: importlib.import_module(
            "langchain_core.documents"
        ).Document(
            page_content=page_content,
            metadata=metadata,
        ),
        delete_kb_directory=lambda *args, **kwargs: delete_kb_directory(*args, **kwargs),
        clear_agent_cache=lambda: _clear_agent_cache(),
        content_hash=lambda value: _content_hash(value),
        audit_security_event=_audit_security_event,
        logger=logger,
    )
)

app.include_router(
    build_chat_router(
        prepare_chat_route_runtime=prepare_chat_route_runtime,
        sse_streaming_response=sse_streaming_response,
        stream_parallel_sse=stream_parallel_sse,
        stream_single_sse=stream_single_sse,
        build_parallel_agent_streams=build_parallel_agent_streams,
        build_single_agent_stream=build_single_agent_stream,
        list_mcp_server_catalog=list_mcp_server_catalog,
        default_mcp_server_names=default_mcp_server_names,
        resolve_active_prompt_runtime=_resolve_active_prompt_runtime,
        validate_chat_payload=_validate_chat_payload,
        prepare_chat_files=_prepare_chat_files,
        build_user_input=_build_user_input,
        base_model_payload=_base_model_payload,
        normalize_model_config=_normalize_model_config,
        model_config_payload=_model_config_payload,
        invoke_agent_stream=_invoke_agent_stream,
        clear_agent_cache=_clear_agent_cache,
        require_remote_admin=_require_remote_admin,
        audit_security_event=_audit_security_event,
        chat_request_model=ChatRequest,
        single_chat_request_model=SingleChatRequest,
        logger=logger,
    )
)

app.include_router(
    build_session_router(
        require_remote_share_secret=_require_remote_share_secret,
        current_share_link_secret=_current_share_link_secret,
        share_link_response_model=ShareLinkResponse,
        share_link_ttl_seconds=SHARE_LINK_TTL_SECONDS,
        request_client_ip=_request_client_ip,
        request_user_agent=_request_user_agent,
        audit_security_event=_audit_security_event,
        token_fingerprint=_token_fingerprint,
        encode_share_token=_encode_share_token,
        build_share_url=_build_share_url,
        create_share_link_payload=create_share_link_payload,
        share_link_store=_share_link_store,
        workspaces_payload=workspaces_payload,
        session_update_requested=session_update_requested,
        create_session_record=create_session_record,
        reorder_sessions_payload=reorder_sessions_payload,
        deck_store=_deck_store,
        tasks_lock=_tasks_lock,
        tasks=_tasks,
        suppressed_task_ids=_suppressed_task_ids,
        prune_task_records_locked=_prune_task_records_locked,
        get_task_store=_get_task_store,
        artifact_store=_artifact_store,
        build_session_messages_payload=_build_session_messages_payload,
        build_answer_group_review_payload=_build_answer_group_review_payload,
        collect_session_attachments=_collect_session_attachments,
        find_session_attachment=_find_session_attachment,
        session_attachments_payload=session_attachments_payload,
        attach_current_kb_status=attach_current_kb_status,
        get_attachment_promotion_task=_get_attachment_promotion_task,
        prepare_attachment_promotion=prepare_attachment_promotion,
        task_record_payload=task_record_payload,
        enqueue_task=enqueue_task,
        persist_task_record=_persist_task_record,
        prune_persisted_tasks=_prune_persisted_tasks,
        run_task=_run_task,
        session_memory_payload=session_memory_payload,
        pin_session_memory_payload=pin_session_memory_payload,
        session_memory_updates=session_memory_updates,
        update_session_memory_payload=update_session_memory_payload,
        summarize_session_memory_payload=summarize_session_memory_payload,
        delete_session_memory_payload=delete_session_memory_payload,
        generate_session_phase_summary_memory=_generate_session_phase_summary_memory,
        validate_chat_payload=_validate_chat_payload,
        base_model_payload=_base_model_payload,
        normalize_model_config=_normalize_model_config,
        model_config_payload=_model_config_payload,
        chat_attachment_preview_chars=CHAT_ATTACHMENT_PREVIEW_CHARS,
        effective_vector_store_path=_effective_vector_store_path,
        require_workspace_session=_require_workspace_session,
        request_field_set=_request_field_set,
        artifact_payload=_artifact_payload,
        clear_agent_cache=_clear_agent_cache,
        create_workspace_request_model=CreateWorkspaceRequest,
        update_workspace_request_model=UpdateWorkspaceRequest,
        create_session_request_model=CreateSessionRequest,
        update_session_request_model=UpdateSessionRequest,
        reorder_sessions_request_model=ReorderSessionsRequest,
        create_bookmark_request_model=CreateBookmarkRequest,
        set_message_feedback_request_model=SetMessageFeedbackRequest,
        truncate_session_messages_request_model=TruncateSessionMessagesRequest,
        import_session_messages_request_model=ImportSessionMessagesRequest,
        set_retrieval_feedback_request_model=SetRetrievalFeedbackRequest,
        pin_session_memory_request_model=PinSessionMemoryRequest,
        update_session_memory_request_model=UpdateSessionMemoryRequest,
        logger=logger,
    )
)

app.include_router(
    build_content_router(
        artifact_store=_artifact_store,
        deck_store=_deck_store,
        share_link_store=_share_link_store,
        tasks=_tasks,
        tasks_lock=_tasks_lock,
        suppressed_task_ids=_suppressed_task_ids,
        prune_task_records_locked=_prune_task_records_locked,
        persist_task_record=_persist_task_record,
        prune_persisted_tasks=_prune_persisted_tasks,
        get_task_store=_get_task_store,
        run_task=_run_task,
        enqueue_task=enqueue_task,
        task_record_payload=task_record_payload,
        list_tasks_payload=list_tasks_payload,
        task_history_limit=TASK_HISTORY_LIMIT,
        artifact_payload=_artifact_payload,
        artifact_export_formats=artifact_export_formats,
        build_deck_artifact=build_deck_artifact,
        build_report_artifact=build_report_artifact,
        sync_deck_artifact=sync_deck_artifact,
        require_remote_viewer=_require_remote_viewer,
        require_remote_editor=_require_remote_editor,
        require_remote_admin=_require_remote_admin,
        require_remote_share_secret=_require_remote_share_secret,
        current_share_link_secret=_current_share_link_secret,
        audit_security_event=_audit_security_event,
        token_fingerprint=_token_fingerprint,
        encode_share_token=_encode_share_token,
        decode_share_token=_decode_share_token,
        build_share_url=_build_share_url,
        create_share_link_payload_fn=create_share_link_payload,
        share_link_ttl_seconds=SHARE_LINK_TTL_SECONDS,
        request_client_ip=_request_client_ip,
        request_user_agent=_request_user_agent,
        share_link_audit_payload=_share_link_audit_payload,
        share_link_response_model=ShareLinkResponse,
        revoke_share_link_response_model=RevokeShareLinkResponse,
        share_link_audit_list_response_model=ShareLinkAuditListResponse,
        open_shared_resource_payload=open_shared_resource_payload,
        build_session_messages_payload=_build_session_messages_payload,
        render_shared_session_html=_render_shared_session_html,
        render_shared_deck_html=_render_shared_deck_html,
        build_download_content_disposition=_build_download_content_disposition,
        build_chat_report_title=build_chat_report_title,
        build_report_markdown=build_report_markdown,
        ensure_deckable_chat=ensure_deckable_chat,
        populate_chat_report_presentation=populate_chat_report_presentation,
        safe_report_filename=safe_report_filename,
        stage_upload_files=stage_upload_files,
        build_upload_documents_task_record=build_upload_documents_task_record,
        cleanup_temp_paths=cleanup_temp_paths,
        upload_documents_response=upload_documents_response,
        effective_vector_store_path=_effective_vector_store_path,
        resolve_report_messages=_resolve_report_messages,
        resolve_active_prompt_runtime=_resolve_active_prompt_runtime,
        normalize_model_config=_resolve_runtime_model_config,
        build_deck=build_deck,
        build_create_deck_kwargs=build_create_deck_kwargs,
        build_regenerate_deck_kwargs=build_regenerate_deck_kwargs,
        apply_deck_update=apply_deck_update,
        replace_deck_slide=replace_deck_slide,
        export_deck_payload=export_deck_payload,
        export_deck_to_pptx=export_deck_to_pptx,
        build_export_filename=build_export_filename,
        normalize_deck_theme=normalize_deck_theme,
        regenerate_deck_slide=regenerate_deck_slide,
        sync_deck_artifacts=_sync_deck_artifacts,
        create_deck_artifact=_create_deck_artifact,
        report_download_payload=report_download_payload,
        resolve_report_messages_fn=_resolve_report_messages,
        create_report_artifact=_create_report_artifact,
        persist_web_research_task_placeholder=persist_web_research_task_placeholder,
        document_upload_max_count=DOCUMENT_UPLOAD_MAX_COUNT,
        document_upload_max_file_bytes=DOCUMENT_UPLOAD_MAX_FILE_BYTES,
        document_upload_max_total_bytes=DOCUMENT_UPLOAD_MAX_TOTAL_BYTES,
        create_task_request_model=CreateTaskRequest,
        create_deck_request_model=CreateDeckRequest,
        update_deck_request_model=UpdateDeckRequest,
        regenerate_deck_slide_request_model=RegenerateDeckSlideRequest,
        generate_report_request_model=GenerateReportRequest,
        update_artifact_request_model=UpdateArtifactRequest,
        generate_artifact_request_model=GenerateArtifactRequest,
        logger=logger,
    )
)


class WorkspaceToolConfigRequest(BaseModel):
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True
    mcp_servers_enabled: list[str] = Field(default_factory=default_mcp_server_names)


class WorkspaceOutputPresetRequest(BaseModel):
    deck_theme: Literal["default", "midnight", "sunrise"] = "default"
    target_slide_count: int = Field(default=8, ge=4, le=10)


class WorkspacePresetRequest(BaseModel):
    default_panels: list[ModelConfig] = Field(default_factory=list)
    tool_config: WorkspaceToolConfigRequest = Field(
        default_factory=WorkspaceToolConfigRequest
    )
    output_preset: WorkspaceOutputPresetRequest = Field(
        default_factory=WorkspaceOutputPresetRequest
    )


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str = ""
    color: str = "blue"
    activate: bool = True
    preset: Optional[WorkspacePresetRequest] = None


class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    preset: Optional[WorkspacePresetRequest] = None


class SetMessageFeedbackRequest(BaseModel):
    value: int
    message_id: Optional[int] = None
    panel_id: str = ""
    answer_group_id: str = ""


class TruncateSessionMessagesRequest(BaseModel):
    answer_group_id: str
    content: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)


class ImportedFileInput(BaseModel):
    name: str
    media_type: str
    data_url: str = ""
    size_bytes: int = 0
    extracted_text: str = ""


class ImportSessionMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[ImportedFileInput] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    model_id: str = ""
    panel_id: str = ""
    answer_group_id: str = ""
    workflow_nodes: list[dict[str, Any]] = Field(default_factory=list)
    task_id: str = ""
    task_type: str = ""


class ImportSessionMessagesRequest(BaseModel):
    panels: list[ModelConfig] = Field(default_factory=list)
    messages: list[ImportSessionMessageRequest] = Field(default_factory=list)


class SetRetrievalFeedbackRequest(BaseModel):
    panel_id: str
    answer_group_id: str
    source: dict[str, Any]
    value: int


class PinSessionMemoryRequest(BaseModel):
    content: str
    kind: str = Field(default="fact")


class UpdateSessionMemoryRequest(BaseModel):
    content: Optional[str] = None
    kind: Optional[str] = None


class GenerateReportRequest(BaseModel):
    session_id: str
    answer_group_id: Optional[str] = None
    panel_id: Optional[str] = None


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


class CreateDeckRequest(BaseModel):
    session_id: str
    panel_config: ModelConfig
    knowledge_base_enabled: bool = True
    target_slide_count: int = Field(default=8, ge=4, le=10)
    theme: str = "default"
    answer_group_id: Optional[str] = None
    panel_id: Optional[str] = None


class GenerateArtifactRequest(BaseModel):
    artifact_type: Literal["report", "deck"]
    session_id: str
    answer_group_id: Optional[str] = None
    panel_id: Optional[str] = None
    panel_config: Optional[ModelConfig] = None
    knowledge_base_enabled: bool = True
    target_slide_count: int = Field(default=8, ge=4, le=10)
    theme: str = "default"


class UpdateArtifactRequest(BaseModel):
    title: Optional[str] = None
    markdown: Optional[str] = None


class UpdateDeckRequest(BaseModel):
    title: Optional[str] = None
    theme: Optional[str] = None
    slides: Optional[list[DeckSlide]] = None


class RegenerateDeckSlideRequest(BaseModel):
    panel_config: ModelConfig
    knowledge_base_enabled: Optional[bool] = None


class CreateTaskRequest(BaseModel):
    task_type: str  # e.g. "analyze_knowledge_base", "generate_report"
    params: dict = {}
    session_id: Optional[str] = None


# ─────────────────────────────────────────────
# 异步任务状态机
# ─────────────────────────────────────────────


def _update_task_progress(record: TaskRecord, progress: int) -> None:
    """线程安全之外的轻量进度更新，供同步处理阶段回调使用。"""
    if record.task_id in _suppressed_task_ids:
        return
    record.progress = max(0, min(100, progress))
    record.updated_at = time.time()
    _persist_task_record(record)


async def _drop_suppressed_task(record: TaskRecord) -> bool:
    if record.task_id not in _suppressed_task_ids:
        return False
    async with _tasks_lock:
        _tasks.pop(record.task_id, None)
        _prune_task_records_locked()
    return True


async def _create_inline_task_record(
    task_type: str,
    params: dict[str, Any],
    *,
    session_id: Optional[str] = None,
    progress: int = 10,
) -> TaskRecord:
    return await create_inline_task_record(
        _tasks,
        _tasks_lock,
        task_type=task_type,
        params=params,
        session_id=session_id,
        progress=progress,
        prune_in_memory=_prune_task_records_locked,
        persist_record=_persist_task_record,
        prune_persisted=_prune_persisted_tasks,
    )


async def _set_inline_task_state(
    record: TaskRecord,
    *,
    status: TaskStatus,
    progress: Optional[int] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> TaskRecord:
    if record.task_id in _suppressed_task_ids:
        async with _tasks_lock:
            _tasks.pop(record.task_id, None)
            _prune_task_records_locked()
        record.status = status
        record.updated_at = time.time()
        if progress is not None:
            record.progress = max(0, min(100, progress))
        if result is not None:
            record.result = result
        if error is not None:
            record.error = error
        return record
    return await set_inline_task_state(
        _tasks,
        _tasks_lock,
        record=record,
        status=status,
        progress=progress,
        result=result,
        error=error,
        prune_in_memory=_prune_task_records_locked,
        persist_record=_persist_task_record,
        prune_persisted=_prune_persisted_tasks,
    )




_tasks: dict[str, TaskRecord] = {}
_tasks_lock = asyncio.Lock()
_suppressed_task_ids: set[str] = set()
_deep_research_semaphore_lock = threading.Lock()
_deep_research_semaphores: dict[int, asyncio.Semaphore] = {}
_task_store: SQLiteTaskStore | None = None
_task_store_init_lock = threading.Lock()


def _is_deep_research_task(record: TaskRecord) -> bool:
    return (
        str(record.task_type or "").strip() == "web_research"
        and str(record.params.get("research_mode") or "").strip().lower() == "deep"
    )


def _get_deep_research_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    loop_key = id(loop)
    with _deep_research_semaphore_lock:
        semaphore = _deep_research_semaphores.get(loop_key)
        if semaphore is None:
            semaphore = asyncio.Semaphore(DEEP_RESEARCH_MAX_CONCURRENCY)
            _deep_research_semaphores[loop_key] = semaphore
        return semaphore


def _get_task_store() -> SQLiteTaskStore:
    global _task_store
    if _task_store is None:
        with _task_store_init_lock:
            if _task_store is None:
                _task_store = SQLiteTaskStore(
                    history_limit=TASK_HISTORY_LIMIT,
                    ttl_seconds=TASK_HISTORY_TTL_SECONDS,
                )
    return _task_store


def _persist_task_record(record: TaskRecord) -> None:
    if record.task_id in _suppressed_task_ids:
        logger.info("Skip persisting suppressed task record: %s", record.task_id)
        return
    try:
        _get_task_store().save(record)
    except Exception:
        logger.exception("Failed to persist task record: %s", record.task_id)


def _prune_persisted_tasks() -> None:
    try:
        _get_task_store().prune()
    except Exception:
        logger.exception("Failed to prune persisted task records")


def _prune_task_records_locked(now: float | None = None) -> None:
    """Prune expired and excess terminal tasks while holding _tasks_lock."""
    prune_task_records(
        _tasks,
        history_limit=TASK_HISTORY_LIMIT,
        ttl_seconds=TASK_HISTORY_TTL_SECONDS,
        now=now,
        logger=logger,
    )


async def _run_task(record: TaskRecord) -> None:
    """后台执行任务并更新状态"""
    deep_research_slot: asyncio.Semaphore | None = None
    deep_research_acquired = False
    try:
        if _is_deep_research_task(record):
            deep_research_slot = _get_deep_research_semaphore()
            await deep_research_slot.acquire()
            deep_research_acquired = True

        async with _tasks_lock:
            _prune_task_records_locked()
            record.status = TaskStatus.RUNNING
            record.updated_at = time.time()
            record.progress = 10
        if await _drop_suppressed_task(record):
            return
        _persist_task_record(record)

        task_type = record.task_type

        async def _set_progress(progress: int) -> None:
            if await _drop_suppressed_task(record):
                return
            async with _tasks_lock:
                record.progress = progress
                record.updated_at = time.time()
            _persist_task_record(record)

        if task_type == "analyze_knowledge_base":
            await run_analyze_knowledge_base_task(
                record,
                set_progress=_set_progress,
                effective_vector_store_path=_effective_vector_store_path,
            )

        elif task_type == "generate_report":
            await run_generate_report_task(
                record,
                set_progress=_set_progress,
                resolve_report_messages=_resolve_report_messages,
                ensure_deckable_chat=ensure_deckable_chat,
                build_chat_report_title=build_chat_report_title,
                build_report_markdown=build_report_markdown,
                build_report_artifact=build_report_artifact,
                save_artifact=_artifact_store.save,
            )

        elif task_type == "generate_deck":
            await run_generate_deck_task(
                record,
                set_progress=_set_progress,
                resolve_report_messages=_resolve_report_messages,
                normalize_model_config=_resolve_runtime_model_config,
                resolve_active_prompt_runtime=_resolve_active_prompt_runtime,
                build_deck=build_deck,
                save_deck=_deck_store.save,
                build_deck_artifact=build_deck_artifact,
                save_artifact=_artifact_store.save,
            )

        elif task_type == "upload_documents":
            await run_upload_documents_task(
                record,
                set_progress=_set_progress,
                update_progress=_update_task_progress,
                effective_vector_store_path=_effective_vector_store_path,
                clear_agent_cache=_clear_agent_cache,
                logger=logger,
            )

        elif task_type == "promote_attachment_to_kb":
            await run_promote_attachment_to_kb_task(
                record,
                set_progress=_set_progress,
                update_progress=_update_task_progress,
                effective_vector_store_path=_effective_vector_store_path,
                chat_file_suffix=_chat_file_suffix,
                decode_data_url=_decode_data_url,
                clear_agent_cache=_clear_agent_cache,
                logger=logger,
            )

        elif task_type == "web_research":
            from agent_core import get_llm

            await run_web_research_task(
                record,
                set_progress=_set_progress,
                normalize_model_config=_resolve_runtime_model_config,
                create_llm=get_llm,
            )

        else:
            await run_placeholder_task(
                record,
                set_progress=_set_progress,
            )

        if await _drop_suppressed_task(record):
            return
        async with _tasks_lock:
            record.status = TaskStatus.COMPLETED
            record.progress = 100
            record.updated_at = time.time()
            _prune_task_records_locked(record.updated_at)
        _persist_task_record(record)
        _prune_persisted_tasks()

    except Exception as exc:
        logger.exception(
            "task_id=%s task_type=%s 执行失败", record.task_id, record.task_type
        )
        if record.task_type == "upload_documents":
            for temp_path in record.params.get("temp_paths", []):
                try:
                    os.remove(str(temp_path))
                except OSError:
                    pass
        if await _drop_suppressed_task(record):
            return
        async with _tasks_lock:
            record.status = TaskStatus.FAILED
            record.error = str(exc)
            record.updated_at = time.time()
            _prune_task_records_locked(record.updated_at)
        _persist_task_record(record)
        if record.task_type == "web_research":
            persist_web_research_task_result(
                record,
                content=f"联网研究任务失败：{record.error}",
                sources=[],
            )
        _prune_persisted_tasks()
    finally:
        if deep_research_slot is not None and deep_research_acquired:
            deep_research_slot.release()


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


def _clip_attachment_preview_text(text: str, limit: int = CHAT_ATTACHMENT_PREVIEW_CHARS) -> str:
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
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if limit <= 0 or len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 3)].rstrip() + "..."


def _summary_llm_enabled() -> bool:
    return summary_llm_enabled()


def _summary_llm_timeout_seconds() -> float:
    return summary_llm_timeout_seconds(12.0)


def _normalize_llm_text_content(content: Any) -> str:
    return normalize_llm_text_content(content)


def _resolve_summary_model_config(
    session_id: str,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> Optional[ModelConfig]:
    from chat_store import get_session_panels

    if preferred_model_config:
        try:
            return _normalize_model_config(ModelConfig(**preferred_model_config))
        except Exception:
            logger.warning("Invalid preferred model config for summary session_id=%s", session_id)

    panels = get_session_panels(session_id)
    if not panels:
        return None

    selected = next((item for item in panels if item.get("is_primary")), panels[0])
    model_config = dict(selected.get("model_config") or {})
    if not str(model_config.get("panel_id") or "").strip():
        model_config["panel_id"] = str(selected.get("panel_id") or "summary")

    try:
        return _normalize_model_config(ModelConfig(**model_config))
    except Exception:
        logger.warning("Cannot resolve summary model config from session panels session_id=%s", session_id)
        return None


def _build_phase_summary_llm_prompt(
    turns: list[dict[str, Any]],
    *,
    total_turns: int,
) -> str:
    return build_phase_summary_llm_prompt(turns, total_turns=total_turns)


async def _try_llm_phase_summary_content(
    session_id: str,
    turns: list[dict[str, Any]],
    *,
    total_turns: int,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    if not _summary_llm_enabled():
        return None

    model_config = _resolve_summary_model_config(
        session_id,
        preferred_model_config=preferred_model_config,
    )
    if model_config is None:
        return None

    from agent_core import get_llm

    try:
        resolved_api_key = _resolve_model_api_key(model_config)
        llm = get_llm(
            provider=model_config.connection_type or model_config.provider,
            model_name=model_config.model,
            base_url=model_config.base_url,
            api_key=resolved_api_key or None,
            temperature=min(max(model_config.temperature, 0.0), 0.4),
        )
        prompt = _build_phase_summary_llm_prompt(turns, total_turns=total_turns)
        timeout_seconds = _summary_llm_timeout_seconds()
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=timeout_seconds)
        content = _normalize_llm_text_content(getattr(response, "content", response))
        content = _clip_text(content, max(120, SESSION_MEMORY_AUTO_SUMMARY_MAX_CONTENT_CHARS))
        if not content:
            return None
        return content
    except Exception:
        logger.warning(
            "LLM summary generation failed, fallback to rule summary session_id=%s",
            session_id,
            exc_info=True,
        )
        return None


def _summary_turns(message_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return summary_turns(message_records, clip_text=_clip_text)


def _build_phase_summary_content(turns: list[dict[str, Any]], *, total_turns: int) -> str:
    return build_phase_summary_content(
        turns,
        total_turns=total_turns,
        clip_text=_clip_text,
        max_chars=SESSION_MEMORY_AUTO_SUMMARY_MAX_CONTENT_CHARS,
    )


async def _generate_session_phase_summary_memory(
    session_id: str,
    *,
    trigger: str,
    force: bool = False,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    from chat_store import (
        SQLiteChatMessageHistory,
        list_session_memory,
        pin_session_memory,
    )

    history = SQLiteChatMessageHistory(session_id=session_id)
    turns = _summary_turns(history.get_all_message_records())
    total_turns = len(turns)
    min_turns = max(2, SESSION_MEMORY_AUTO_SUMMARY_MIN_TURNS)

    if not force and total_turns < min_turns:
        raise ValueError(
            f"Need at least {min_turns} conversation turns before generating a phase summary memory."
        )

    summaries = list_session_memory(
        session_id,
        kind="summary",
        newest_first=True,
        db_path=history.db_path,
    )
    latest_auto = latest_auto_summary(summaries)
    covered_turns = covered_turns_from_summary(latest_auto)

    new_turns = max(0, total_turns - covered_turns)
    min_new_turns = max(1, SESSION_MEMORY_AUTO_SUMMARY_MIN_NEW_TURNS)
    if latest_auto and not force and new_turns < min_new_turns:
        return {
            "created": False,
            "memory": latest_auto,
            "reason": "up_to_date",
            "stats": {
                "total_turns": total_turns,
                "new_turns": new_turns,
                "required_new_turns": min_new_turns,
            },
        }

    window_size = max(2, SESSION_MEMORY_AUTO_SUMMARY_WINDOW_SIZE)
    window_turns = turns[-window_size:]
    content = _build_phase_summary_content(window_turns, total_turns=total_turns)
    generator = "rules"
    llm_content = await _try_llm_phase_summary_content(
        session_id,
        window_turns,
        total_turns=total_turns,
        preferred_model_config=preferred_model_config,
    )
    if llm_content:
        content = llm_content
        generator = "llm"
    meta = summarize_window_meta(
        total_turns=total_turns,
        trigger=trigger,
        generator=generator,
        window_turns=window_turns,
    )
    result = pin_session_memory(
        session_id,
        content=content,
        kind="summary",
        meta=meta,
        db_path=history.db_path,
    )
    if not result:
        return None
    return {
        **result,
        "reason": "created" if result.get("created") else "deduped",
        "stats": {
            "total_turns": total_turns,
            "new_turns": new_turns,
            "required_new_turns": min_new_turns,
        },
    }


async def _auto_generate_phase_summary_memory(
    session_id: str,
    *,
    trigger: str,
    preferred_model_config: Optional[dict[str, Any]] = None,
) -> None:
    try:
        result = await _generate_session_phase_summary_memory(
            session_id,
            trigger=trigger,
            force=False,
            preferred_model_config=preferred_model_config,
        )
        if result and result.get("created"):
            logger.info("Auto summary memory created session_id=%s", session_id)
    except ValueError:
        # Session not long enough yet.
        return
    except Exception:
        logger.exception("Auto summary memory generation failed session_id=%s", session_id)


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
    from agent_core import build_agent

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
        if 'dashboard_task_record' in locals() and dashboard_task_record is not None:
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

_frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    from fastapi.responses import FileResponse

    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_frontend_dist, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = os.path.join(_frontend_dist, "index.html")
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        reload=True,
    )
