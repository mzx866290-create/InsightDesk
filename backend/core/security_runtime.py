"""Security, auth, share-link, and audit runtime helpers.

Functions receive the API server module as ``ctx`` to preserve backwards-compatible
monkeypatching of private helpers during the ongoing api_server split.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request


def _hash_secret(ctx, secret: str) -> str:
    if not secret:
        return "no-key"
    return ctx.hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _token_fingerprint(ctx, token: str) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return "empty"
    return ctx.hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _token_preview(ctx, token: str) -> str:
    normalized = str(token or "").strip()
    if len(normalized) <= 10:
        return normalized
    return f"{normalized[:6]}...{normalized[-4:]}"


def _auth_token_preview(ctx, token: str) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return "empty"
    if len(normalized) <= 4:
        return "*" * len(normalized)
    if len(normalized) <= 8:
        return f"{normalized[:2]}...{normalized[-2:]}"
    return f"{normalized[:4]}...{normalized[-2:]}"


def _request_client_ip(ctx, request: Request) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client is not None else ""
    return str(host or "").strip()


def _request_user_agent(ctx, request: Request) -> str:
    return str(request.headers.get("user-agent") or "").strip()


def _request_is_local(ctx, request: Request) -> bool:
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client is not None else ""
    return ctx._is_loopback_host(host)


def _current_admin_api_token(ctx) -> str:
    return str(ctx.os.getenv("ADMIN_API_TOKEN", "") or "").strip()


def _normalize_auth_role(ctx, role: Any, *, default: str | None = None) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in ctx.AUTH_ROLE_RANKS:
        return normalized
    return ctx.DEFAULT_AUTH_ROLE if default is None else default


def _role_rank(ctx, role: str) -> int:
    return ctx.AUTH_ROLE_RANKS.get(ctx._normalize_auth_role(role), 0)


def _sanitize_log_value(ctx, value: Any, *, max_length: int = 256) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = ctx.re.sub("[\\r\\n\\t]+", " ", text)
    text = ctx.re.sub("\\s{2,}", " ", text)
    if len(text) > max_length:
        return f"{text[: max_length - 3]}..."
    return text


def _auth_capabilities_for_role(ctx, role: str) -> list[str]:
    return ctx._build_auth_capabilities_for_role(
        role, normalize_auth_role=ctx._normalize_auth_role, role_rank=ctx._role_rank
    )


def _auth_token_is_weak(ctx, token: Any) -> bool:
    normalized = str(token or "").strip()
    return len(normalized) < ctx.MIN_AUTH_TOKEN_RECOMMENDED_LENGTH


def _auth_token_hygiene_summary(
    ctx, auth_records: list[dict[str, str]] | None = None
) -> dict[str, int | bool]:
    records = (
        auth_records
        if auth_records is not None
        else ctx._configured_auth_token_records()
    )
    weak_count = 0
    legacy_count = 0
    for record in records:
        token = record.get("token") or ""
        auth_source = str(record.get("auth_source") or "").strip()
        if ctx._auth_token_is_weak(token):
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
        normalized_role = ctx._normalize_auth_role(role)
        normalized_user_id = ctx._sanitize_log_value(
            user_id or ctx.DEFAULT_AUTH_USER_IDS[normalized_role], max_length=128
        )
        token_records[normalized_token] = {
            "token": normalized_token,
            "role": normalized_role,
            "user_id": normalized_user_id,
            "auth_source": ctx._sanitize_log_value(auth_source, max_length=64)
            or "token_catalog",
        }

    raw_catalog = str(ctx.os.getenv("APP_AUTH_TOKENS_JSON", "") or "").strip()
    if raw_catalog:
        try:
            parsed_catalog = ctx.json.loads(raw_catalog)
        except ctx.json.JSONDecodeError:
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
        ctx._current_admin_api_token(),
        role="admin",
        user_id="admin",
        auth_source="legacy_admin_token",
    )
    _add_token_record(
        ctx.os.getenv("EDITOR_API_TOKEN"),
        role="editor",
        user_id="editor",
        auth_source="legacy_editor_token",
    )
    _add_token_record(
        ctx.os.getenv("VIEWER_API_TOKEN"),
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
        for record in ctx._configured_auth_token_records()
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
    return ctx._extract_request_token(request)


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
    return ctx._request_auth_mode(request)


def _resolve_request_auth(ctx, request: Request) -> dict[str, Any]:
    cached = getattr(request.state, "resolved_auth", None)
    if isinstance(cached, dict):
        return cached
    is_local_request = ctx._request_is_local(request)
    bypass_enabled = not ctx.ALLOW_REMOTE_CLIENTS or is_local_request
    auth_mode = ctx._request_auth_mode(request)
    token_present = False
    token_valid = False
    trusted_user_id = ""
    trusted_role = ""
    trusted_source = ""
    if bypass_enabled:
        trusted_user_id = (
            ctx._sanitize_log_value(request.headers.get("X-User-Id"), max_length=128)
            or "local"
        )
        trusted_role = "admin"
        trusted_source = "local_bypass" if is_local_request else "local_only_mode"
        token_valid = True
    else:
        request_token = ctx._extract_request_token(request)
        token_present = bool(request_token)
        auth_record = ctx._configured_auth_token_map().get(request_token)
        if auth_record is not None:
            trusted_user_id = str(auth_record.get("user_id") or "").strip()
            trusted_role = ctx._normalize_auth_role(auth_record.get("role"))
            trusted_source = str(auth_record.get("auth_source") or "").strip()
            token_valid = True
        elif hasattr(ctx, "_resolve_sso_session_token"):
            auth_record = ctx._resolve_sso_session_token(request_token)
            if auth_record is not None:
                trusted_user_id = str(auth_record.get("user_id") or "").strip()
                trusted_role = ctx._normalize_auth_role(auth_record.get("role"))
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
    return str(ctx._resolve_request_auth(request).get("user_id") or "").strip()


def _request_user_role(ctx, request: Request) -> str:
    return str(ctx._resolve_request_auth(request).get("role") or "").strip()


def _request_auth_source(ctx, request: Request) -> str:
    return str(ctx._resolve_request_auth(request).get("auth_source") or "").strip()


def _sanitize_request_path(ctx, path: str) -> str:
    normalized = str(path or "").strip() or "/"
    if normalized.startswith("/api/share-links/"):
        return "/api/share-links/<token>"
    if normalized.startswith("/shared/"):
        return "/shared/<token>"
    return normalized


def _remote_management_rate_limit_applies(ctx, request: Request) -> bool:
    if not ctx.REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED:
        return False
    if not ctx.ALLOW_REMOTE_CLIENTS or ctx._request_is_local(request):
        return False
    if str(request.method or "").strip().upper() == "OPTIONS":
        return False
    path = ctx._sanitize_request_path(request.url.path)
    return any(
        (
            path.startswith(prefix)
            for prefix in ctx._REMOTE_MANAGEMENT_RATE_LIMIT_PATH_PREFIXES
        )
    )


def _remote_management_rate_limit_principal(ctx, request: Request) -> str:
    token = ctx._extract_request_token(request)
    if token:
        return f"token:{ctx._token_fingerprint(token)}"
    ip = ctx._request_client_ip(request) or "unknown"
    return f"ip:{ip}"


def _ceil_seconds(ctx, seconds: float) -> int:
    normalized = float(seconds or 0.0)
    if normalized <= 0:
        return 0
    truncated = int(normalized)
    if float(truncated) < normalized:
        truncated += 1
    return max(1, truncated)


def _consume_remote_management_rate_limit(
    ctx, request: Request
) -> dict[str, Any] | None:
    if not ctx._remote_management_rate_limit_applies(request):
        return None
    now = ctx.time.time()
    window_seconds = int(ctx.REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS)
    max_requests = int(ctx.REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS)
    principal = ctx._remote_management_rate_limit_principal(request)
    path = ctx._sanitize_request_path(request.url.path)
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
            ctx._remote_management_rate_limits[principal] = state
        remaining = max(0, max_requests - current_count)
        reset_after_seconds = max(
            0.0,
            float(window_seconds)
            - (now - float(state.get("window_started_at", now) or now)),
        )
        retry_after = ctx._ceil_seconds(reset_after_seconds) if not allowed else 0
    return {
        "allowed": bool(allowed),
        "principal": principal,
        "path": path,
        "limit": max_requests,
        "remaining": remaining,
        "window_seconds": window_seconds,
        "retry_after": retry_after,
        "reset_after_seconds": ctx._ceil_seconds(reset_after_seconds),
    }


def _current_share_link_secret(ctx) -> str:
    return str(ctx.os.getenv("SHARE_LINK_SECRET", ctx.SHARE_LINK_SECRET) or "").strip()


def _share_link_secret_is_weak(ctx) -> bool:
    secret = ctx._current_share_link_secret()
    return (
        not secret
        or secret == ctx.DEFAULT_SHARE_LINK_SECRET
        or len(secret) < ctx.MIN_SHARE_LINK_SECRET_LENGTH
    )


def _require_remote_role(
    ctx, request: Request, *, minimum_role: str = "admin"
) -> dict[str, Any]:
    auth = ctx._resolve_request_auth(request)
    if auth["bypass_enabled"]:
        return auth
    configured_records = ctx._configured_auth_token_records()
    if not configured_records and not auth["token_valid"]:
        ctx._audit_security_event(
            "remote_auth_guard",
            request,
            result="blocked",
            details=f"reason=auth_not_configured required_role={minimum_role}",
        )
        raise ctx.HTTPException(
            status_code=503,
            detail="Remote access is disabled until API tokens are configured.",
        )
    if not auth["token_valid"]:
        reason = "missing_token" if not auth["token_present"] else "invalid_token"
        ctx._audit_security_event(
            "remote_auth_guard",
            request,
            result="rejected",
            details=f"reason={reason} required_role={minimum_role}",
        )
        raise ctx.HTTPException(status_code=403, detail="Missing or invalid API token.")
    actual_role = str(auth["role"] or "").strip()
    if ctx._role_rank(actual_role) < ctx._role_rank(minimum_role):
        ctx._audit_security_event(
            "remote_auth_guard",
            request,
            result="rejected",
            details=f"reason=insufficient_role required_role={minimum_role} actual_role={actual_role or '<none>'}",
        )
        raise ctx.HTTPException(
            status_code=403, detail=f"Insufficient role: {minimum_role} required."
        )
    return auth


def _require_remote_viewer(ctx, request: Request) -> dict[str, Any]:
    return ctx._require_remote_role(request, minimum_role="viewer")


def _require_remote_editor(ctx, request: Request) -> dict[str, Any]:
    return ctx._require_remote_role(request, minimum_role="editor")


def _require_remote_admin(ctx, request: Request) -> dict[str, Any]:
    return ctx._require_remote_role(request, minimum_role="admin")


def _require_remote_share_secret(ctx, request: Request) -> None:
    if not ctx.ALLOW_REMOTE_CLIENTS or ctx._request_is_local(request):
        return
    if ctx._share_link_secret_is_weak():
        ctx._audit_security_event(
            "remote_share_guard",
            request,
            result="blocked",
            details="reason=weak_share_link_secret",
        )
        raise ctx.HTTPException(
            status_code=503,
            detail="Remote sharing is disabled until SHARE_LINK_SECRET is strong enough.",
        )


def _content_hash(ctx, value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        payload = value
    else:
        payload = ctx.json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return ctx.hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audit_security_event(
    ctx, action: str, request: Request, *, result: str = "ok", details: str = ""
) -> None:
    request_id = getattr(request.state, "request_id", "")
    event = {
        "timestamp": ctx.time.time(),
        "request_id": str(request_id or "").strip(),
        "action": ctx._sanitize_log_value(action, max_length=128),
        "result": ctx._sanitize_log_value(result, max_length=32),
        "ip": ctx._sanitize_log_value(ctx._request_client_ip(request), max_length=64),
        "is_local": bool(ctx._request_is_local(request)),
        "auth_mode": ctx._sanitize_log_value(
            ctx._request_auth_mode(request), max_length=32
        ),
        "auth_source": ctx._sanitize_log_value(
            ctx._request_auth_source(request), max_length=64
        ),
        "user_id": ctx._sanitize_log_value(
            ctx._request_user_id(request), max_length=128
        ),
        "user_role": ctx._sanitize_log_value(
            ctx._request_user_role(request), max_length=64
        ),
        "details": ctx._sanitize_log_value(details, max_length=512),
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
        "created_user_agent": str(
            getattr(record, "created_user_agent", "") or ""
        ).strip(),
        "access_count": int(getattr(record, "access_count", 0) or 0),
        "last_accessed_at": float(getattr(record, "last_accessed_at", 0))
        if getattr(record, "last_accessed_at", None) is not None
        else None,
        "last_accessed_ip": str(getattr(record, "last_accessed_ip", "") or "").strip(),
        "last_accessed_user_agent": str(
            getattr(record, "last_accessed_user_agent", "") or ""
        ).strip(),
        "share_token_preview": ctx._token_preview(share_token),
        "share_token_fingerprint": ctx._token_fingerprint(share_token),
    }


def _security_status_payload(ctx) -> dict[str, Any]:
    cors_origins, cors_allow_credentials = ctx._cors_settings()
    return ctx._build_security_status_payload(
        allow_remote_clients=ctx.ALLOW_REMOTE_CLIENTS,
        share_link_ttl_seconds=ctx.SHARE_LINK_TTL_SECONDS,
        remote_management_rate_limit_enabled=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED,
        remote_management_rate_limit_window_seconds=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS,
        remote_management_rate_limit_window_seconds_source=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS_SOURCE,
        remote_management_rate_limit_max_requests=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS,
        remote_management_rate_limit_max_requests_source=ctx.REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS_SOURCE,
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
        configured_auth_token_records=ctx._configured_auth_token_records,
        auth_token_hygiene_summary=ctx._auth_token_hygiene_summary,
        role_rank=ctx._role_rank,
        share_link_secret_is_weak=ctx._share_link_secret_is_weak,
        read_security_audit_event_count=lambda: (
            ctx._get_security_audit_store().count_events()
        ),
        logger=ctx.logger,
    )


def _auth_token_catalog_payload(ctx) -> dict[str, Any]:
    return ctx._build_auth_token_catalog_payload(
        default_role=ctx.DEFAULT_AUTH_ROLE,
        configured_auth_token_records=ctx._configured_auth_token_records,
        auth_token_hygiene_summary=ctx._auth_token_hygiene_summary,
        auth_token_preview=ctx._auth_token_preview,
        token_fingerprint=ctx._token_fingerprint,
        auth_token_is_weak=ctx._auth_token_is_weak,
        role_rank=ctx._role_rank,
    )


def _safe_epoch_seconds(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _security_audit_event_to_payload(record: Any) -> dict[str, Any]:
    return {
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
        "tenant_id": getattr(record, "tenant_id", "") or "",
        "org_id": getattr(record, "org_id", "") or "",
        "legal_hold": bool(getattr(record, "legal_hold", False)),
    }


def _security_audit_detail_value(ctx, details: Any, *names: str) -> str:
    normalized_names = {str(name or "").strip().lower() for name in names}
    for match in ctx.re.finditer(
        r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>[^ ]*)",
        str(details or ""),
    ):
        key = str(match.group("key") or "").strip().lower()
        if key in normalized_names:
            return str(match.group("value") or "").strip()
    return ""


def _security_audit_event_org(event: dict[str, Any]) -> str:
    return str(event.get("org_id") or "").strip()


def _security_audit_event_tenant(event: dict[str, Any]) -> str:
    tenant = str(event.get("tenant_id") or "").strip()
    return tenant or _security_audit_event_org(event)


def _security_audit_redacted_details(ctx, details: Any) -> str:
    """Keep detail context useful for SIEM while removing obvious secrets."""

    text = ctx._sanitize_log_value(details, max_length=512)
    if not text:
        return ""
    sensitive_key_pattern = (
        r"(?i)\b(token|secret|password|passwd|authorization|api[_-]?key|"
        r"client[_-]?secret|state|nonce|code|session[_-]?token)=([^ ]+)"
    )
    text = ctx.re.sub(sensitive_key_pattern, lambda match: f"{match.group(1)}=<redacted>", text)
    text = ctx.re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer <redacted>", text)
    return text


def _security_audit_siem_event_payload(
    ctx, event: dict[str, Any]
) -> dict[str, Any]:
    action = ctx._sanitize_log_value(event.get("action"), max_length=128)
    result = ctx._sanitize_log_value(event.get("result"), max_length=32)
    org_id = _security_audit_event_org(event) or _security_audit_detail_value(
        ctx, event.get("details"), "org_id", "org", "organization_id"
    )
    tenant_id = _security_audit_event_tenant(event) or _security_audit_detail_value(
        ctx, event.get("details"), "tenant_id", "tenant"
    )
    if not tenant_id and org_id:
        tenant_id = org_id
    return {
        "time": float(_safe_epoch_seconds(event.get("timestamp")) or 0.0),
        "request_id": ctx._sanitize_log_value(event.get("request_id"), max_length=128),
        "action": action,
        "result": result,
        "category": ctx._security_audit_category_for_action(action),
        "user_id": ctx._sanitize_log_value(event.get("user_id"), max_length=128),
        "user_role": ctx._sanitize_log_value(event.get("user_role"), max_length=64),
        "tenant": ctx._sanitize_log_value(tenant_id, max_length=128),
        "tenant_id": ctx._sanitize_log_value(tenant_id, max_length=128),
        "org": ctx._sanitize_log_value(org_id, max_length=128),
        "org_id": ctx._sanitize_log_value(org_id, max_length=128),
        "ip": ctx._sanitize_log_value(event.get("ip"), max_length=64),
        "auth_mode": ctx._sanitize_log_value(event.get("auth_mode"), max_length=32),
        "auth_source": ctx._sanitize_log_value(
            event.get("auth_source"), max_length=64
        ),
        "legal_hold": bool(event.get("legal_hold")),
        "details": _security_audit_redacted_details(ctx, event.get("details")),
    }


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
    normalized_action = str(action or "").strip().lower()
    normalized_result = str(result or "").strip().lower()
    normalized_category = str(category or "").strip().lower()
    normalized_user_id = str(user_id or "").strip()

    filtered: list[dict[str, Any]] = []
    for item in events:
        item_action = str(item.get("action") or "").strip()
        if normalized_action and item_action.lower() != normalized_action:
            continue
        item_result = str(item.get("result") or "").strip().lower()
        if normalized_result and item_result != normalized_result:
            continue
        if normalized_category:
            event_category = ctx._security_audit_category_for_action(item_action)
            if event_category != normalized_category:
                continue
        item_user_id = str(item.get("user_id") or "").strip()
        if normalized_user_id and item_user_id != normalized_user_id:
            continue
        timestamp = _safe_epoch_seconds(item.get("timestamp")) or 0.0
        if since is not None and timestamp < since:
            continue
        if until is not None and timestamp > until:
            continue
        filtered.append(item)
    return filtered


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

    return ctx._build_security_audit_summary_payload(
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
    normalized_format = str(format or "json").strip().lower()
    if normalized_format not in {"json", "ndjson"}:
        normalized_format = "json"
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
    exported_events = [_security_audit_siem_event_payload(ctx, event) for event in events]
    content = ""
    if normalized_format == "ndjson":
        content = "\n".join(
            ctx.json.dumps(event, ensure_ascii=False, sort_keys=True)
            for event in exported_events
        )
    return {
        "format": normalized_format,
        "content_type": (
            "application/x-ndjson"
            if normalized_format == "ndjson"
            else "application/json"
        ),
        "events": exported_events if normalized_format == "json" else [],
        "content": content,
        "total": len(exported_events),
        "limit": normalized_limit,
        "filters": filters,
    }


def _increment_nested_count(
    totals: dict[str, dict[str, int]], dimension: str, value: Any, count: int = 1
) -> None:
    bucket = totals.setdefault(dimension, {})
    key = str(value or "unknown").strip() or "unknown"
    bucket[key] = bucket.get(key, 0) + int(count)


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
    groups: dict[tuple[str, str, str, str, str, str], int] = {}
    totals: dict[str, dict[str, int]] = {}
    for event in events:
        siem_event = _security_audit_siem_event_payload(ctx, event)
        key = (
            str(siem_event["tenant"] or "unknown"),
            str(siem_event["org"] or "unknown"),
            str(siem_event["user_id"] or "unknown"),
            str(siem_event["category"] or "uncategorized"),
            str(siem_event["action"] or "unknown"),
            str(siem_event["result"] or "unknown"),
        )
        groups[key] = groups.get(key, 0) + 1
    rows = [
        {
            "tenant": tenant,
            "org": org,
            "user_id": grouped_user_id,
            "category": grouped_category,
            "action": grouped_action,
            "result": grouped_result,
            "count": count,
        }
        for (
            tenant,
            org,
            grouped_user_id,
            grouped_category,
            grouped_action,
            grouped_result,
        ), count in sorted(groups.items())
    ]
    for row in rows:
        for dimension in ("tenant", "org", "user_id", "category", "action", "result"):
            _increment_nested_count(totals, dimension, row[dimension], row["count"])
    return {
        "total": len(events),
        "window_limit": normalized_limit,
        "group_by": ["tenant", "org", "user_id", "category", "action", "result"],
        "rows": rows,
        "totals": {key: dict(sorted(value.items())) for key, value in totals.items()},
        "filters": filters,
    }


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
    cutoff_timestamp = (
        ctx.time.time() - float(normalized_retention_days * 86400)
        if normalized_retention_days > 0
        else None
    )
    try:
        stored_events = ctx._get_security_audit_store().list_events(
            limit=int(ctx.SECURITY_AUDIT_HISTORY_LIMIT)
        )
    except Exception:
        ctx.logger.exception("Failed to load persisted security audit events")
        stored_events = []
    events = [_security_audit_event_to_payload(record) for record in stored_events]
    legal_hold_count = sum(1 for event in events if bool(event.get("legal_hold")))
    candidates = [
        event
        for event in events
        if not bool(event.get("legal_hold"))
        and (
            cutoff_timestamp is None
            or float(_safe_epoch_seconds(event.get("timestamp")) or 0.0)
            <= cutoff_timestamp
        )
    ]
    legal_hold_preserved_count = sum(
        1
        for event in events
        if bool(event.get("legal_hold"))
        and (
            cutoff_timestamp is None
            or float(_safe_epoch_seconds(event.get("timestamp")) or 0.0)
            <= cutoff_timestamp
        )
    )
    export_events = (
        [_security_audit_siem_event_payload(ctx, event) for event in candidates[:normalized_limit]]
        if normalized_mode == "export"
        else []
    )
    return {
        "mode": normalized_mode,
        "retention_days": normalized_retention_days,
        "cutoff_timestamp": cutoff_timestamp,
        "history_limit": int(ctx.SECURITY_AUDIT_HISTORY_LIMIT),
        "total": len(events),
        "archive_candidate_count": len(candidates),
        "export_count": len(export_events),
        "legal_hold_count": int(legal_hold_count),
        "legal_hold_preserved_count": int(legal_hold_preserved_count),
        "cleanup_behavior": {
            "manual_cleanup_endpoint": "/api/security/audit-events/cleanup",
            "cleanup_preserves_legal_hold": True,
            "existing_cleanup_contract": "keep_latest and dry_run parameters are unchanged",
            "legal_hold_requested": bool(legal_hold),
        },
        "events": export_events,
    }


def _security_audit_legal_hold_payload(
    ctx, *, request_id: str, legal_hold: bool = True
) -> dict[str, Any]:
    normalized_request_id = ctx._sanitize_log_value(request_id, max_length=128)
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
