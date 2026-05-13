"""Security, auth, share-link, and audit runtime helpers.

Functions receive a narrow runtime context instead of the full API server module.
The context is a dynamic proxy, so existing tests can still monkeypatch private
helpers while the allowed dependency surface stays explicit.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from fastapi import HTTPException, Request

from backend.core import env_runtime, model_config_runtime, request_runtime
from backend.helpers.security_helpers import (
    auth_token_is_weak,
    auth_token_preview,
    build_auth_token_catalog_payload,
    build_security_audit_summary_payload,
    build_security_audit_aggregate_report_payload,
    build_security_audit_archive_policy_payload,
    build_security_audit_siem_export_payload,
    build_security_status_payload,
    build_sso_config_payload,
    ceil_seconds,
    normalize_auth_role,
    normalize_sso_config_update as normalize_sso_config_update_value,
    role_rank,
    sanitize_log_value,
    sanitize_request_path,
    share_link_audit_payload,
    security_audit_detail_value,
    security_audit_event_org,
    security_audit_event_tenant,
    security_audit_event_to_payload,
    security_audit_redacted_details,
    security_audit_siem_event_payload,
    filter_security_audit_events,
    safe_epoch_seconds,
    token_fingerprint,
    token_preview,
)

SECURITY_RUNTIME_CONTEXT_ATTRIBUTES = (
    "ALLOW_REMOTE_CLIENTS", "AUTH_ROLE_RANKS", "CHAT_ATTACHMENT_PREVIEW_CHARS", "CHAT_FILE_MAX_BYTES",
    "CHAT_FILE_MAX_CHARS_PER_FILE", "CHAT_FILE_MAX_COUNT", "CHAT_FILE_MAX_TOTAL_CHARS", "DEFAULT_AUTH_ROLE",
    "DEFAULT_AUTH_USER_IDS", "DEFAULT_SHARE_LINK_SECRET", "DOCUMENT_UPLOAD_MAX_COUNT", "DOCUMENT_UPLOAD_MAX_FILE_BYTES",
    "DOCUMENT_UPLOAD_MAX_TOTAL_BYTES", "MIN_AUTH_TOKEN_RECOMMENDED_LENGTH", "MIN_SHARE_LINK_SECRET_LENGTH",
    "REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED", "REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS", "REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS_SOURCE", "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS",
    "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE", "SECURITY_AUDIT_HISTORY_LIMIT", "SECURITY_AUDIT_HISTORY_LIMIT_SOURCE", "SECURITY_AUDIT_MEMORY_WINDOW_LIMIT",
    "SHARE_LINK_SECRET", "SHARE_LINK_TTL_SECONDS", "_REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES",
    "_get_security_audit_store", "_persist_security_audit_event",
    "_effective_sso_config_value", "_effective_sso_session_ttl_seconds",
    "_set_sso_config_field",
    "_remote_management_rate_limit_lock", "_remote_management_rate_limits",
    "_request_is_local", "_resolve_sso_session_token",
    "_security_audit_events", "_security_audit_events_lock",
    "logger", "time",
)


class SecurityRuntimeContext:
    """Whitelist-backed dynamic proxy for security runtime dependencies."""

    __slots__ = ("_allowed_attributes", "_source")

    def __init__(
        self,
        source: Any,
        allowed_attributes: tuple[str, ...] = SECURITY_RUNTIME_CONTEXT_ATTRIBUTES,
    ) -> None:
        self._source = source
        self._allowed_attributes = frozenset(allowed_attributes)

    def __getattr__(self, name: str) -> Any:
        if name not in self._allowed_attributes:
            raise AttributeError(f"Security runtime context has no dependency {name!r}")
        return getattr(self._source, name)


def build_security_runtime_context(source: Any) -> SecurityRuntimeContext:
    missing = [
        attribute
        for attribute in SECURITY_RUNTIME_CONTEXT_ATTRIBUTES
        if not hasattr(source, attribute)
    ]
    if missing:
        raise AttributeError(
            "Security runtime context missing required attributes: " + ", ".join(missing)
        )
    return SecurityRuntimeContext(source)


def _request_is_local(ctx, request: Request) -> bool:
    return env_runtime.is_loopback_host(request_runtime.request_client_ip(request))


def _current_admin_api_token(ctx) -> str:
    return str(os.getenv("ADMIN_API_TOKEN", "") or "").strip()


def _normalize_auth_role(ctx, role: Any, *, default: str | None = None) -> str:
    return normalize_auth_role(
        role,
        role_ranks=ctx.AUTH_ROLE_RANKS,
        default=ctx.DEFAULT_AUTH_ROLE if default is None else default,
    )


def _role_rank(ctx, role: str) -> int:
    return role_rank(
        role,
        role_ranks=ctx.AUTH_ROLE_RANKS,
        normalize_role=lambda value: _normalize_auth_role(ctx, value),
    )


def _auth_token_is_weak(ctx, token: Any) -> bool:
    return auth_token_is_weak(
        token, min_length=ctx.MIN_AUTH_TOKEN_RECOMMENDED_LENGTH
    )


def _auth_token_hygiene_summary(
    ctx, auth_records: list[dict[str, str]] | None = None
) -> dict[str, int | bool]:
    records = (
        auth_records
        if auth_records is not None
        else _configured_auth_token_records(ctx)
    )
    weak_count = 0
    legacy_count = 0
    for record in records:
        token = record.get("token") or ""
        auth_source = str(record.get("auth_source") or "").strip()
        if _auth_token_is_weak(ctx, token):
            weak_count += 1
        if auth_source.startswith("legacy_"):
            legacy_count += 1
    return {
        "weak_count": int(weak_count),
        "legacy_count": int(legacy_count),
        "healthy": weak_count == 0 and legacy_count == 0,
    }


def _configured_auth_token_records(ctx) -> list[dict[str, str]]:
    token_records: dict[str, dict[str, str]] = {}

    def _add_token_record(
        token: Any, *, role: Any, user_id: Any = "", auth_source: Any = ""
    ) -> None:
        normalized_token = str(token or "").strip()
        if not normalized_token or normalized_token in token_records:
            return
        normalized_role = _normalize_auth_role(ctx, role)
        normalized_user_id = sanitize_log_value(
            user_id or ctx.DEFAULT_AUTH_USER_IDS[normalized_role], max_length=128
        )
        token_records[normalized_token] = {
            "token": normalized_token,
            "role": normalized_role,
            "user_id": normalized_user_id,
            "auth_source": sanitize_log_value(auth_source, max_length=64)
            or "token_catalog",
        }

    raw_catalog = str(os.getenv("APP_AUTH_TOKENS_JSON", "") or "").strip()
    if raw_catalog:
        try:
            parsed_catalog = json.loads(raw_catalog)
        except json.JSONDecodeError:
            ctx.logger.warning("Failed to parse APP_AUTH_TOKENS_JSON")
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
        _current_admin_api_token(ctx),
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


def _configured_auth_token_map(ctx) -> dict[str, dict[str, str]]:
    return {
        record["token"]: {
            "role": record["role"],
            "user_id": record["user_id"],
            "auth_source": record["auth_source"],
        }
        for record in _configured_auth_token_records(ctx)
    }


def _extract_request_token(ctx, request: Request) -> str:
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


def _extract_admin_token(ctx, request: Request) -> str:
    return _extract_request_token(ctx, request)


def _request_auth_mode(ctx, request: Request) -> str:
    if not ctx.ALLOW_REMOTE_CLIENTS:
        return "local_only_mode"
    if ctx._request_is_local(request):
        return "local"
    if str(request.headers.get("X-API-Token") or "").strip():
        return "header"
    if str(request.headers.get("X-Admin-Token") or "").strip():
        return "header"
    authorization = str(request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return "bearer"
    return "missing"


def _admin_auth_mode(ctx, request: Request) -> str:
    return _request_auth_mode(ctx, request)


def _resolve_request_auth(ctx, request: Request) -> dict[str, Any]:
    cached = getattr(request.state, "resolved_auth", None)
    if isinstance(cached, dict):
        return cached
    is_local_request = ctx._request_is_local(request)
    bypass_enabled = not ctx.ALLOW_REMOTE_CLIENTS or is_local_request
    auth_mode = _request_auth_mode(ctx, request)
    token_present = False
    token_valid = False
    trusted_user_id = ""
    trusted_role = ""
    trusted_source = ""
    if bypass_enabled:
        trusted_user_id = (
            sanitize_log_value(request.headers.get("X-User-Id"), max_length=128)
            or "local"
        )
        trusted_role = "admin"
        trusted_source = "local_bypass" if is_local_request else "local_only_mode"
        token_valid = True
    else:
        request_token = _extract_request_token(ctx, request)
        token_present = bool(request_token)
        auth_record = _configured_auth_token_map(ctx).get(request_token)
        if auth_record is not None:
            trusted_user_id = str(auth_record.get("user_id") or "").strip()
            trusted_role = _normalize_auth_role(ctx, auth_record.get("role"))
            trusted_source = str(auth_record.get("auth_source") or "").strip()
            token_valid = True
        elif hasattr(ctx, "_resolve_sso_session_token"):
            auth_record = ctx._resolve_sso_session_token(request_token)
            if auth_record is not None:
                trusted_user_id = str(auth_record.get("user_id") or "").strip()
                trusted_role = _normalize_auth_role(ctx, auth_record.get("role"))
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


def _request_user_id(ctx, request: Request) -> str:
    return str(_resolve_request_auth(ctx, request).get("user_id") or "").strip()


def _request_user_role(ctx, request: Request) -> str:
    return str(_resolve_request_auth(ctx, request).get("role") or "").strip()


def _request_auth_source(ctx, request: Request) -> str:
    return str(_resolve_request_auth(ctx, request).get("auth_source") or "").strip()


def _remote_management_rate_limit_applies(ctx, request: Request) -> bool:
    if not ctx.REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED:
        return False
    if not ctx.ALLOW_REMOTE_CLIENTS or ctx._request_is_local(request):
        return False
    if str(request.method or "").strip().upper() == "OPTIONS":
        return False
    path = sanitize_request_path(request.url.path)
    return any(
        (
            path.startswith(prefix)
            for prefix in ctx._REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES
        )
    )


def _remote_management_rate_limit_principal(ctx, request: Request) -> str:
    token = _extract_request_token(ctx, request)
    if token:
        return f"token:{token_fingerprint(token)}"
    ip = request_runtime.request_client_ip(request) or "unknown"
    return f"ip:{ip}"


def _consume_remote_management_rate_limit(
    ctx, request: Request
) -> dict[str, Any] | None:
    if not _remote_management_rate_limit_applies(ctx, request):
        return None
    now = ctx.time.time()
    window_seconds = int(ctx.REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS)
    max_requests = int(ctx.REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS)
    principal = _remote_management_rate_limit_principal(ctx, request)
    path = sanitize_request_path(request.url.path)
    with ctx._remote_management_rate_limit_lock:
        expired_cutoff = now - float(window_seconds)
        stale_principals = [
            key
            for key, value in ctx._remote_management_rate_limits.items()
            if float(value.get("window_started_at", 0.0) or 0.0) <= expired_cutoff
        ]
        for key in stale_principals:
            ctx._remote_management_rate_limits.pop(key, None)
        state = ctx._remote_management_rate_limits.get(principal)
        if state is None or now - float(
            state.get("window_started_at", 0.0) or 0.0
        ) >= float(window_seconds):
            state = {"window_started_at": float(now), "count": 0.0}
        current_count = int(state.get("count", 0.0) or 0)
        allowed = current_count < max_requests
        if allowed:
            current_count += 1
            state["count"] = float(current_count)
            ctx._remote_management_rate_limits[principal] = state
        else:
            state["blocked_count"] = float(int(state.get("blocked_count", 0.0) or 0) + 1)
            state["last_blocked_at"] = float(now)
            ctx._remote_management_rate_limits[principal] = state
        remaining = max(0, max_requests - current_count)
        reset_after_seconds = max(
            0.0,
            float(window_seconds)
            - (now - float(state.get("window_started_at", now) or now)),
        )
        retry_after = ceil_seconds(reset_after_seconds) if not allowed else 0
    return {
        "allowed": bool(allowed),
        "principal": principal,
        "path": path,
        "limit": max_requests,
        "remaining": remaining,
        "window_seconds": window_seconds,
        "retry_after": retry_after,
        "reset_after_seconds": ceil_seconds(reset_after_seconds),
    }


def _remote_management_rate_limit_status(ctx) -> dict[str, Any]:
    now = ctx.time.time()
    window_seconds = int(ctx.REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS)
    with ctx._remote_management_rate_limit_lock:
        expired_cutoff = now - float(window_seconds)
        stale_principals = [
            key
            for key, value in ctx._remote_management_rate_limits.items()
            if float(value.get("window_started_at", 0.0) or 0.0) <= expired_cutoff
        ]
        for key in stale_principals:
            ctx._remote_management_rate_limits.pop(key, None)

        active_states = list(ctx._remote_management_rate_limits.values())
        blocked_count = sum(
            int(value.get("blocked_count", 0.0) or 0) for value in active_states
        )
        last_blocked_values = [
            float(value.get("last_blocked_at", 0.0) or 0.0)
            for value in active_states
            if float(value.get("last_blocked_at", 0.0) or 0.0) > 0
        ]
        reset_after_values = [
            ceil_seconds(
                max(
                    0.0,
                    float(window_seconds)
                    - (now - float(value.get("window_started_at", now) or now)),
                )
            )
            for value in active_states
        ]

    return {
        "path_prefixes": list(ctx._REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES),
        "response_headers": [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-RateLimit-Scope",
            "Retry-After",
        ],
        "tracked_principal_count": len(active_states),
        "active_request_count": sum(
            int(value.get("count", 0.0) or 0) for value in active_states
        ),
        "blocked_count": blocked_count,
        "last_blocked_at": max(last_blocked_values) if last_blocked_values else None,
        "next_reset_after_seconds": min(reset_after_values) if reset_after_values else 0,
    }


def _current_share_link_secret(ctx) -> str:
    return str(os.getenv("SHARE_LINK_SECRET", ctx.SHARE_LINK_SECRET) or "").strip()


def _share_link_secret_is_weak(ctx) -> bool:
    secret = _current_share_link_secret(ctx)
    return (
        not secret
        or secret == ctx.DEFAULT_SHARE_LINK_SECRET
        or len(secret) < ctx.MIN_SHARE_LINK_SECRET_LENGTH
    )


def _share_link_secret_uses_default(ctx) -> bool:
    return _current_share_link_secret(ctx) == ctx.DEFAULT_SHARE_LINK_SECRET


def _require_remote_role(
    ctx, request: Request, *, minimum_role: str = "admin"
) -> dict[str, Any]:
    auth = _resolve_request_auth(ctx, request)
    if auth["bypass_enabled"]:
        return auth
    configured_records = _configured_auth_token_records(ctx)
    if not configured_records and not auth["token_valid"]:
        _audit_security_event(
            ctx,
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
            ctx,
            "remote_auth_guard",
            request,
            result="rejected",
            details=f"reason={reason} required_role={minimum_role}",
        )
        raise HTTPException(status_code=403, detail="Missing or invalid API token.")
    actual_role = str(auth["role"] or "").strip()
    if _role_rank(ctx, actual_role) < _role_rank(ctx, minimum_role):
        _audit_security_event(
            ctx,
            "remote_auth_guard",
            request,
            result="rejected",
            details=f"reason=insufficient_role required_role={minimum_role} actual_role={actual_role or '<none>'}",
        )
        raise HTTPException(
            status_code=403, detail=f"Insufficient role: {minimum_role} required."
        )
    return auth


def _require_remote_viewer(ctx, request: Request) -> dict[str, Any]:
    return _require_remote_role(ctx, request, minimum_role="viewer")


def _require_remote_editor(ctx, request: Request) -> dict[str, Any]:
    return _require_remote_role(ctx, request, minimum_role="editor")


def _require_remote_admin(ctx, request: Request) -> dict[str, Any]:
    return _require_remote_role(ctx, request, minimum_role="admin")


def _require_remote_share_secret(ctx, request: Request) -> None:
    if not ctx.ALLOW_REMOTE_CLIENTS or ctx._request_is_local(request):
        return
    if _share_link_secret_is_weak(ctx):
        _audit_security_event(
            ctx,
            "remote_share_guard",
            request,
            result="blocked",
            details="reason=weak_share_link_secret",
        )
        raise HTTPException(
            status_code=503,
            detail="Remote sharing is disabled until SHARE_LINK_SECRET is strong enough.",
        )


def _audit_security_event(
    ctx, action: str, request: Request, *, result: str = "ok", details: str = ""
) -> None:
    request_id = getattr(request.state, "request_id", "")
    event = {
        "timestamp": ctx.time.time(),
        "request_id": str(request_id or "").strip(),
        "action": sanitize_log_value(action, max_length=128),
        "result": sanitize_log_value(result, max_length=32),
        "ip": sanitize_log_value(request_runtime.request_client_ip(request), max_length=64),
        "is_local": bool(ctx._request_is_local(request)),
        "auth_mode": sanitize_log_value(
            _request_auth_mode(ctx, request), max_length=32
        ),
        "auth_source": sanitize_log_value(
            _request_auth_source(ctx, request), max_length=64
        ),
        "user_id": sanitize_log_value(
            _request_user_id(ctx, request), max_length=128
        ),
        "user_role": sanitize_log_value(
            _request_user_role(ctx, request), max_length=64
        ),
        "details": sanitize_log_value(details, max_length=512),
    }
    with ctx._security_audit_events_lock:
        ctx._security_audit_events.append(event)
        del ctx._security_audit_events[: -ctx.SECURITY_AUDIT_MEMORY_WINDOW_LIMIT]
    ctx._persist_security_audit_event(event)
    ctx.logger.info(
        "security_event action=%s result=%s request_id=%s ip=%s local=%s auth=%s auth_source=%s user_id=%s user_role=%s details=%s",
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


def _share_link_audit_payload(
    ctx, record: Any, *, now: Optional[float] = None
) -> dict[str, Any]:
    current_time = ctx.time.time() if now is None else float(now)
    return share_link_audit_payload(
        record,
        current_time=current_time,
        token_preview_func=token_preview,
        token_fingerprint_func=token_fingerprint,
    )


def _security_status_payload(ctx) -> dict[str, Any]:
    cors_origins, cors_allow_credentials = env_runtime.cors_settings()
    return build_security_status_payload(
        allow_remote_clients=ctx.ALLOW_REMOTE_CLIENTS,
        share_link_ttl_seconds=ctx.SHARE_LINK_TTL_SECONDS,
        remote_management_rate_limit_enabled=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED,
        remote_management_rate_limit_window_seconds=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS,
        remote_management_rate_limit_window_seconds_source=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE,
        remote_management_rate_limit_max_requests=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS,
        remote_management_rate_limit_max_requests_source=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS_SOURCE,
        remote_management_rate_limit_status=_remote_management_rate_limit_status(ctx),
        security_audit_history_limit=ctx.SECURITY_AUDIT_HISTORY_LIMIT,
        security_audit_history_limit_source=ctx.SECURITY_AUDIT_HISTORY_LIMIT_SOURCE,
        security_audit_memory_window_limit=ctx.SECURITY_AUDIT_MEMORY_WINDOW_LIMIT,
        chat_file_limits={
            "max_count": int(ctx.CHAT_FILE_MAX_COUNT),
            "max_bytes": int(ctx.CHAT_FILE_MAX_BYTES),
            "max_chars_per_file": int(ctx.CHAT_FILE_MAX_CHARS_PER_FILE),
            "max_total_chars": int(ctx.CHAT_FILE_MAX_TOTAL_CHARS),
            "preview_chars": int(ctx.CHAT_ATTACHMENT_PREVIEW_CHARS),
        },
        document_upload_limits={
            "max_count": int(ctx.DOCUMENT_UPLOAD_MAX_COUNT),
            "max_file_bytes": int(ctx.DOCUMENT_UPLOAD_MAX_FILE_BYTES),
            "max_total_bytes": int(ctx.DOCUMENT_UPLOAD_MAX_TOTAL_BYTES),
        },
        cors_allowed_origins=cors_origins,
        cors_allow_credentials=cors_allow_credentials,
        configured_auth_token_records=lambda: _configured_auth_token_records(ctx),
        auth_token_hygiene_summary=lambda auth_records=None: (
            _auth_token_hygiene_summary(ctx, auth_records)
        ),
        role_rank=lambda value: _role_rank(ctx, value),
        share_link_secret_is_weak=lambda: _share_link_secret_is_weak(ctx),
        share_link_secret_uses_default=lambda: _share_link_secret_uses_default(ctx),
        min_share_link_secret_length=ctx.MIN_SHARE_LINK_SECRET_LENGTH,
        read_security_audit_event_count=lambda: (
            ctx._get_security_audit_store().count_events()
        ),
        logger=ctx.logger,
    )


def _sso_config_payload(ctx) -> dict[str, Any]:
    return build_sso_config_payload(
        provider=ctx._effective_sso_config_value("provider"),
        issuer_url=ctx._effective_sso_config_value("issuer_url"),
        authorization_endpoint=ctx._effective_sso_config_value(
            "authorization_endpoint"
        ),
        token_endpoint=ctx._effective_sso_config_value("token_endpoint"),
        jwks_url=ctx._effective_sso_config_value("jwks_url"),
        client_id=ctx._effective_sso_config_value("client_id"),
        client_secret=ctx._effective_sso_config_value("client_secret"),
        allowed_domains=ctx._effective_sso_config_value("allowed_domains"),
        scopes=ctx._effective_sso_config_value("scopes"),
        default_role=_normalize_auth_role(
            ctx,
            ctx._effective_sso_config_value("default_role"),
            default=ctx.DEFAULT_AUTH_ROLE,
        ),
        session_ttl_seconds=ctx._effective_sso_session_ttl_seconds(),
    )


def _normalize_sso_config_update(ctx, field: str, value: Any) -> str:
    try:
        return normalize_sso_config_update_value(
            field,
            value,
            default_auth_role=ctx.DEFAULT_AUTH_ROLE,
            normalize_auth_role=lambda role, *, default=ctx.DEFAULT_AUTH_ROLE: (
                _normalize_auth_role(ctx, role, default=default)
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _save_sso_config_payload(ctx, body: Any) -> dict[str, Any]:
    data = model_config_runtime.base_model_payload(body)
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
        ctx._set_sso_config_field(
            field,
            _normalize_sso_config_update(ctx, field, data[field]),
        )

    client_secret = data.get("client_secret")
    if clear_client_secret:
        ctx._set_sso_config_field("client_secret", "")
    elif client_secret is not None and str(client_secret or "").strip():
        ctx._set_sso_config_field("client_secret", str(client_secret or "").strip())

    return _sso_config_payload(ctx)


def _auth_token_catalog_payload(ctx) -> dict[str, Any]:
    return build_auth_token_catalog_payload(
        default_role=ctx.DEFAULT_AUTH_ROLE,
        configured_auth_token_records=lambda: _configured_auth_token_records(ctx),
        auth_token_hygiene_summary=lambda auth_records=None: (
            _auth_token_hygiene_summary(ctx, auth_records)
        ),
        auth_token_preview=auth_token_preview,
        token_fingerprint=token_fingerprint,
        auth_token_is_weak=lambda token: _auth_token_is_weak(ctx, token),
        role_rank=lambda value: _role_rank(ctx, value),
    )


def _safe_epoch_seconds(value: Any) -> float | None:
    return safe_epoch_seconds(value)


def _security_audit_event_to_payload(record: Any) -> dict[str, Any]:
    return security_audit_event_to_payload(record)


def _security_audit_detail_value(ctx, details: Any, *names: str) -> str:
    return security_audit_detail_value(details, *names)


def _security_audit_event_org(event: dict[str, Any]) -> str:
    return security_audit_event_org(event)


def _security_audit_event_tenant(event: dict[str, Any]) -> str:
    return security_audit_event_tenant(event)


def _security_audit_redacted_details(ctx, details: Any) -> str:
    return security_audit_redacted_details(details)


def _security_audit_siem_event_payload(
    ctx, event: dict[str, Any]
) -> dict[str, Any]:
    return security_audit_siem_event_payload(event)


def _security_audit_load_filtered_events(
    ctx,
    *,
    limit: int = 50,
    action: str = "",
    result: str = "",
    category: str = "",
    user_id: str = "",
    since: Any = None,
    until: Any = None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    max_limit = int(ctx.SECURITY_AUDIT_HISTORY_LIMIT)
    try:
        max_limit = max(max_limit, int(ctx._get_security_audit_store().history_limit))
    except Exception:
        ctx.logger.exception("Failed to read security audit history limit")
    normalized_limit = max(1, min(int(limit or 50), max_limit))
    normalized_action = str(action or "").strip().lower()
    normalized_result = str(result or "").strip().lower()
    normalized_category = str(category or "").strip().lower()
    normalized_user_id = str(user_id or "").strip()
    normalized_since = _safe_epoch_seconds(since)
    normalized_until = _safe_epoch_seconds(until)
    if (
        normalized_since is not None
        and normalized_until is not None
        and normalized_since > normalized_until
    ):
        normalized_since, normalized_until = normalized_until, normalized_since
    try:
        stored_events = ctx._get_security_audit_store().list_events(
            limit=max_limit,
            action=normalized_action,
            result=normalized_result,
        )
    except Exception:
        ctx.logger.exception("Failed to load persisted security audit events")
        stored_events = []
    if stored_events:
        events = [_security_audit_event_to_payload(record) for record in stored_events]
    else:
        with ctx._security_audit_events_lock:
            events = [dict(item) for item in ctx._security_audit_events]
    events = _filter_security_audit_events(
        ctx,
        events,
        action=normalized_action,
        result=normalized_result,
        category=normalized_category,
        user_id=normalized_user_id,
        since=normalized_since,
        until=normalized_until,
    )
    filters = {
        "action": normalized_action,
        "result": normalized_result,
        "category": normalized_category,
        "user_id": normalized_user_id,
        "since": normalized_since,
        "until": normalized_until,
    }
    return events[-normalized_limit:], normalized_limit, filters


def _filter_security_audit_events(
    ctx,
    events: list[dict[str, Any]],
    *,
    action: str = "",
    result: str = "",
    category: str = "",
    user_id: str = "",
    since: float | None = None,
    until: float | None = None,
) -> list[dict[str, Any]]:
    return filter_security_audit_events(
        events,
        action=action,
        result=result,
        category=category,
        user_id=user_id,
        since=since,
        until=until,
    )


def _security_audit_events_payload(
    ctx,
    *,
    limit: int = 50,
    action: str = "",
    result: str = "",
    category: str = "",
    user_id: str = "",
    since: Any = None,
    until: Any = None,
) -> dict[str, Any]:
    max_limit = int(ctx.SECURITY_AUDIT_HISTORY_LIMIT)
    try:
        max_limit = max(max_limit, int(ctx._get_security_audit_store().history_limit))
    except Exception:
        ctx.logger.exception("Failed to read security audit history limit")
    normalized_limit = max(1, min(int(limit or 50), max_limit))
    normalized_action = str(action or "").strip().lower()
    normalized_result = str(result or "").strip().lower()
    normalized_category = str(category or "").strip().lower()
    normalized_user_id = str(user_id or "").strip()
    normalized_since = _safe_epoch_seconds(since)
    normalized_until = _safe_epoch_seconds(until)
    if (
        normalized_since is not None
        and normalized_until is not None
        and normalized_since > normalized_until
    ):
        normalized_since, normalized_until = normalized_until, normalized_since
    try:
        stored_events = ctx._get_security_audit_store().list_events(
            limit=max_limit,
            action=normalized_action,
            result=normalized_result,
        )
    except Exception:
        ctx.logger.exception("Failed to load persisted security audit events")
        stored_events = []
    if stored_events:
        events = [_security_audit_event_to_payload(record) for record in stored_events]
    else:
        with ctx._security_audit_events_lock:
            events = [dict(item) for item in ctx._security_audit_events]
    events = _filter_security_audit_events(
        ctx,
        events,
        action=normalized_action,
        result=normalized_result,
        category=normalized_category,
        user_id=normalized_user_id,
        since=normalized_since,
        until=normalized_until,
    )
    events = events[-normalized_limit:]
    return {
        "events": events,
        "total": len(events),
        "limit": normalized_limit,
        "filters": {
            "action": normalized_action,
            "result": normalized_result,
            "category": normalized_category,
            "user_id": normalized_user_id,
            "since": normalized_since,
            "until": normalized_until,
        },
    }


def _security_audit_summary_payload(
    ctx, *, category: str = "", limit: int = 0
) -> dict[str, Any]:
    max_limit = int(ctx.SECURITY_AUDIT_HISTORY_LIMIT)
    try:
        max_limit = max(max_limit, int(ctx._get_security_audit_store().history_limit))
    except Exception:
        ctx.logger.exception("Failed to read security audit history limit")
    normalized_limit = max(1, min(int(limit or max_limit), max_limit))
    try:
        stored_events = ctx._get_security_audit_store().list_events(
            limit=normalized_limit
        )
    except Exception:
        ctx.logger.exception("Failed to load persisted security audit events")
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
            }
            for record in stored_events
        ]
    else:
        with ctx._security_audit_events_lock:
            events = [
                {key: value for key, value in dict(item).items() if key != "details"}
                for item in ctx._security_audit_events[-normalized_limit:]
            ]

    return build_security_audit_summary_payload(
        events,
        category=category,
        window_limit=normalized_limit,
    )


def _security_audit_siem_export_payload(
    ctx,
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
    events, normalized_limit, filters = _security_audit_load_filtered_events(
        ctx,
        limit=limit,
        action=action,
        result=result,
        category=category,
        user_id=user_id,
        since=since,
        until=until,
    )
    return build_security_audit_siem_export_payload(
        events,
        format=format,
        limit=normalized_limit,
        filters=filters,
    )


def _security_audit_aggregate_report_payload(
    ctx,
    *,
    limit: int = 0,
    action: str = "",
    result: str = "",
    category: str = "",
    user_id: str = "",
    since: Any = None,
    until: Any = None,
) -> dict[str, Any]:
    max_limit = int(ctx.SECURITY_AUDIT_HISTORY_LIMIT)
    try:
        max_limit = max(max_limit, int(ctx._get_security_audit_store().history_limit))
    except Exception:
        ctx.logger.exception("Failed to read security audit history limit")
    events, normalized_limit, filters = _security_audit_load_filtered_events(
        ctx,
        limit=limit or max_limit,
        action=action,
        result=result,
        category=category,
        user_id=user_id,
        since=since,
        until=until,
    )
    return build_security_audit_aggregate_report_payload(
        events,
        limit=normalized_limit,
        filters=filters,
    )


def _security_audit_archive_policy_payload(
    ctx,
    *,
    mode: str = "preview",
    retention_days: int = 365,
    limit: int = 100,
    legal_hold: bool = False,
) -> dict[str, Any]:
    normalized_mode = str(mode or "preview").strip().lower()
    if normalized_mode not in {"preview", "export"}:
        normalized_mode = "preview"
    normalized_retention_days = max(0, int(retention_days or 0))
    normalized_limit = max(1, min(int(limit or 100), int(ctx.SECURITY_AUDIT_HISTORY_LIMIT)))
    current_time = ctx.time.time()
    try:
        stored_events = ctx._get_security_audit_store().list_events(
            limit=int(ctx.SECURITY_AUDIT_HISTORY_LIMIT)
        )
    except Exception:
        ctx.logger.exception("Failed to load persisted security audit events")
        stored_events = []
    events = [_security_audit_event_to_payload(record) for record in stored_events]
    return build_security_audit_archive_policy_payload(
        events,
        mode=normalized_mode,
        retention_days=normalized_retention_days,
        current_time=current_time,
        limit=normalized_limit,
        history_limit=int(ctx.SECURITY_AUDIT_HISTORY_LIMIT),
        legal_hold=legal_hold,
    )


def _security_audit_legal_hold_payload(
    ctx, *, request_id: str, legal_hold: bool = True
) -> dict[str, Any]:
    normalized_request_id = sanitize_log_value(request_id, max_length=128)
    updated_count = ctx._get_security_audit_store().set_legal_hold(
        normalized_request_id,
        legal_hold=bool(legal_hold),
    )
    return {
        "request_id": normalized_request_id,
        "legal_hold": bool(legal_hold),
        "updated_count": int(updated_count),
    }


def _cleanup_security_audit_events(
    ctx, *, keep_latest: int = 0, dry_run: bool = False
) -> dict[str, Any]:
    normalized_keep_latest = max(
        0, min(int(keep_latest or 0), int(ctx.SECURITY_AUDIT_HISTORY_LIMIT))
    )
    before_count = ctx._get_security_audit_store().count_events()
    would_delete_count = max(0, int(before_count) - int(normalized_keep_latest))
    if dry_run:
        deleted_count = 0
        remaining_count = before_count
    else:
        deleted_count = ctx._get_security_audit_store().trim_to_latest(
            normalized_keep_latest
        )
        remaining_count = ctx._get_security_audit_store().count_events()
    with ctx._security_audit_events_lock:
        memory_before_count = len(ctx._security_audit_events)
        if not dry_run:
            if normalized_keep_latest <= 0:
                ctx._security_audit_events.clear()
            else:
                ctx._security_audit_events[:] = ctx._security_audit_events[
                    -normalized_keep_latest:
                ]
        memory_remaining_count = len(ctx._security_audit_events)
    return {
        "keep_latest": normalized_keep_latest,
        "dry_run": bool(dry_run),
        "would_delete_count": int(would_delete_count),
        "deleted_count": int(deleted_count),
        "remaining_count": int(remaining_count),
        "memory_deleted_count": int(
            max(0, memory_before_count - memory_remaining_count)
        ),
        "memory_remaining_count": int(memory_remaining_count),
        "history_limit": int(ctx.SECURITY_AUDIT_HISTORY_LIMIT),
    }
