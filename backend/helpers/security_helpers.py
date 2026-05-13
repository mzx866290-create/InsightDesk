from __future__ import annotations

"""Security helper utilities."""

import base64
import hashlib
import json
import logging
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlencode


AUTH_ROLE_RANKS = {"viewer": 1, "editor": 2, "admin": 3}
RESOURCE_ROLE_RANKS = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}

RESOURCE_PERMISSION_OPERATIONS = (
    {
        "operation": "read_resource",
        "minimum_role": "viewer",
        "description": "Read a protected resource when an explicit ACL exists.",
    },
    {
        "operation": "create_derived_resource",
        "minimum_role": "viewer",
        "description": "Create a task, report, deck, or artifact from a readable source.",
    },
    {
        "operation": "update_resource",
        "minimum_role": "editor",
        "description": "Mutate resource content, metadata, messages, memory, or deck slides.",
    },
    {
        "operation": "manage_resource_grants",
        "minimum_role": "admin",
        "description": "Create, update, or delete user and organization resource grants.",
    },
    {
        "operation": "own_resource",
        "minimum_role": "owner",
        "description": "Anchor the resource ACL and protect against removing the last owner.",
    },
)

SECURITY_AUDIT_ACTIONS = (
    {
        "action": "remote_auth_guard",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "Remote authentication guard rejected, blocked, or allowed a request.",
    },
    {
        "action": "remote_management_rate_limit",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "Remote management rate limiting blocked or allowed a guarded request.",
    },
    {
        "action": "remote_share_guard",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "Remote share-link safety checks blocked or allowed share access.",
    },
    {
        "action": "get_security_status",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "A caller read the security readiness and guard health payload.",
    },
    {
        "action": "get_auth_whoami",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "A caller read their resolved authenticated identity.",
    },
    {
        "action": "get_auth_tokens",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "An admin inspected the configured token catalog without raw secrets.",
    },
    {
        "action": "get_auth_sso_config",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "A caller read the public SSO/OIDC readiness configuration.",
    },
    {
        "action": "update_auth_sso_config",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "An admin updated persisted SSO/OIDC runtime configuration without exposing secrets.",
    },
    {
        "action": "start_auth_sso_login",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "A caller requested an OIDC authorization URL with state, nonce, and PKCE metadata.",
    },
    {
        "action": "complete_auth_sso_callback",
        "category": "auth",
        "minimum_reader_role": "admin",
        "description": "An OIDC authorization callback exchanged code, verified ID token claims, and synced identity.",
    },
    {
        "action": "get_identity_catalog",
        "category": "identity",
        "minimum_reader_role": "admin",
        "description": "A caller listed organizations, users, and memberships.",
    },
    {
        "action": "upsert_identity_org",
        "category": "identity",
        "minimum_reader_role": "admin",
        "description": "An admin created or updated an organization record.",
    },
    {
        "action": "upsert_identity_user",
        "category": "identity",
        "minimum_reader_role": "admin",
        "description": "An admin created or updated a user record.",
    },
    {
        "action": "set_identity_membership",
        "category": "identity",
        "minimum_reader_role": "admin",
        "description": "An admin assigned or changed an organization membership role.",
    },
    {
        "action": "sync_external_identity",
        "category": "identity",
        "minimum_reader_role": "admin",
        "description": "An admin synced verified external identity claims into local users and memberships.",
    },
    {
        "action": "list_resource_grants",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "A caller listed resource grants with optional filters.",
    },
    {
        "action": "get_resource_access",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "A caller resolved their effective role on a resource.",
    },
    {
        "action": "upsert_resource_grant",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "An admin created, changed, or attempted to downgrade a resource grant.",
    },
    {
        "action": "delete_resource_grant",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "An admin deleted or attempted to delete a resource grant.",
    },
    {
        "action": "resource_access_denied",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "A resource ACL check rejected a caller for insufficient role.",
    },
    {
        "action": "resource_owner_granted",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "A newly created resource received its creator owner grant.",
    },
    {
        "action": "resource_grants_inherited",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "A derived resource copied explicit grants from its source.",
    },
    {
        "action": "get_access_role_matrix",
        "category": "access",
        "minimum_reader_role": "admin",
        "description": "A caller read the resource role-to-operation permission matrix.",
    },
    {
        "action": "get_security_audit_actions",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin listed known security audit action names and categories.",
    },
    {
        "action": "get_security_audit_events",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin listed raw security audit events with optional filters.",
    },
    {
        "action": "get_security_audit_summary",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin read aggregated security audit counts without raw event details.",
    },
    {
        "action": "export_security_audit_siem",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin exported redacted security audit events for SIEM ingestion.",
    },
    {
        "action": "get_security_audit_aggregate_report",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin read cross-tenant security audit counts grouped by tenant, org, user, category, action, and result.",
    },
    {
        "action": "get_security_audit_archive_policy",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin previewed security audit archival, retention, and legal-hold preservation policy.",
    },
    {
        "action": "set_security_audit_legal_hold",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin marked or released a security audit event legal hold by request id.",
    },
    {
        "action": "task_approval_decision",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "A human reviewer approved or rejected a single task approval request.",
    },
    {
        "action": "task_approval_batch_decision",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "A human reviewer approved or rejected multiple task approval requests in one batch.",
    },
    {
        "action": "task_approval_policy_update",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin updated the runtime policy for task approval gates.",
    },
    {
        "action": "cleanup_security_audit_events",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin trimmed persisted and in-memory security audit history.",
    },
)


def _csv_values(value: Any) -> list[str]:
    return [
        item
        for raw_item in str(value or "").split(",")
        if (item := raw_item.strip().lower())
    ]


def _scope_values(value: list[str] | str) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(",", " ").split()
    else:
        raw_items = value
    return [item for raw_item in raw_items if (item := str(raw_item or "").strip())]


def hash_secret(secret: str) -> str:
    if not secret:
        return "no-key"
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def token_fingerprint(token: Any) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return "empty"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def token_preview(token: Any) -> str:
    normalized = str(token or "").strip()
    if len(normalized) <= 10:
        return normalized
    return f"{normalized[:6]}...{normalized[-4:]}"


def auth_token_preview(token: Any) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return "empty"
    if len(normalized) <= 4:
        return "*" * len(normalized)
    if len(normalized) <= 8:
        return f"{normalized[:2]}...{normalized[-2:]}"
    return f"{normalized[:4]}...{normalized[-2:]}"


def normalize_auth_role(
    role: Any,
    *,
    role_ranks: Mapping[str, int] = AUTH_ROLE_RANKS,
    default: str = "viewer",
) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in role_ranks:
        return normalized
    return default


def role_rank(
    role: Any,
    *,
    role_ranks: Mapping[str, int] = AUTH_ROLE_RANKS,
    normalize_role: Callable[[Any], str] | None = None,
    default_auth_role: str = "viewer",
) -> int:
    if normalize_role is not None:
        normalized_role = normalize_role(role)
    else:
        normalized_role = normalize_auth_role(
            role, role_ranks=role_ranks, default=default_auth_role
        )
    return int(role_ranks.get(normalized_role, 0))


def sanitize_log_value(value: Any, *, max_length: int = 256) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub("[\\r\\n\\t]+", " ", text)
    text = re.sub("\\s{2,}", " ", text)
    if len(text) > max_length:
        return f"{text[: max_length - 3]}..."
    return text


def sanitize_request_path(path: Any) -> str:
    normalized = str(path or "").strip() or "/"
    if normalized.startswith("/api/share-links/"):
        return "/api/share-links/<token>"
    if normalized.startswith("/shared/"):
        return "/shared/<token>"
    return normalized


def auth_token_is_weak(token: Any, *, min_length: int = 16) -> bool:
    normalized = str(token or "").strip()
    return len(normalized) < min_length


def ceil_seconds(seconds: float) -> int:
    normalized = float(seconds or 0.0)
    if normalized <= 0:
        return 0
    truncated = int(normalized)
    if float(truncated) < normalized:
        truncated += 1
    return max(1, truncated)


def content_hash(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        payload = value
    else:
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def auth_capabilities_for_role(
    role: str,
    *,
    normalize_auth_role: Callable[..., str],
    role_rank: Callable[[str], int],
) -> list[str]:
    normalized_role = normalize_auth_role(role)
    capabilities: list[str] = ["read_auth_profile"]
    if role_rank(normalized_role) >= role_rank("viewer"):
        capabilities.extend(
            [
                "read_security_status",
                "read_operations_runtime",
                "read_documents",
                "read_prompts",
                "read_knowledge_bases",
                "test_retrieval",
            ]
        )
    if role_rank(normalized_role) >= role_rank("editor"):
        capabilities.extend(
            [
                "upload_documents",
                "manage_prompts",
                "edit_knowledge_base_chunks",
            ]
        )
    if role_rank(normalized_role) >= role_rank("admin"):
        capabilities.extend(
            [
                "manage_config",
                "reset_agents",
                "delete_knowledge_base",
                "manage_share_links",
            ]
        )
    return capabilities


def build_auth_whoami_payload(
    auth: Mapping[str, Any],
    *,
    default_role: str,
    normalize_auth_role: Callable[..., str],
    role_rank: Callable[[str], int],
) -> dict[str, Any]:
    normalized_role = normalize_auth_role(auth.get("role"), default=default_role)
    return {
        "user_id": str(auth.get("user_id") or "").strip(),
        "role": normalized_role,
        "auth_mode": str(auth.get("auth_mode") or "").strip(),
        "auth_source": str(auth.get("auth_source") or "").strip(),
        "is_local": bool(auth.get("is_local")),
        "capabilities": auth_capabilities_for_role(
            normalized_role,
            normalize_auth_role=normalize_auth_role,
            role_rank=role_rank,
        ),
    }


def build_security_status_payload(
    *,
    allow_remote_clients: bool,
    share_link_ttl_seconds: int,
    remote_management_rate_limit_enabled: bool,
    remote_management_rate_limit_window_seconds: int,
    remote_management_rate_limit_window_seconds_source: str,
    remote_management_rate_limit_max_requests: int,
    remote_management_rate_limit_max_requests_source: str,
    remote_management_rate_limit_status: Mapping[str, Any],
    security_audit_history_limit: int,
    security_audit_history_limit_source: str,
    security_audit_memory_window_limit: int,
    chat_file_limits: dict[str, int],
    document_upload_limits: dict[str, int],
    cors_allowed_origins: list[str],
    cors_allow_credentials: bool,
    configured_auth_token_records: Callable[[], list[dict[str, str]]],
    auth_token_hygiene_summary: Callable[[list[dict[str, str]] | None], dict[str, int | bool]],
    role_rank: Callable[[str], int],
    share_link_secret_is_weak: Callable[[], bool],
    share_link_secret_uses_default: Callable[[], bool],
    min_share_link_secret_length: int,
    read_security_audit_event_count: Callable[[], int],
    logger: logging.Logger,
) -> dict[str, Any]:
    auth_records = configured_auth_token_records()
    auth_token_hygiene = auth_token_hygiene_summary(auth_records)
    configured_roles = sorted({record["role"] for record in auth_records}, key=role_rank)
    admin_token_configured = any(record["role"] == "admin" for record in auth_records)
    share_link_secret_healthy = not share_link_secret_is_weak()
    security_audit_persisted_count = 0
    try:
        security_audit_persisted_count = read_security_audit_event_count()
    except Exception:
        logger.exception("Failed to read security audit event count")

    return {
        "allow_remote_clients": allow_remote_clients,
        "local_only_mode": not allow_remote_clients,
        "remote_auth_ready": (not allow_remote_clients) or bool(auth_records),
        "admin_token_configured": admin_token_configured,
        "remote_admin_ready": (not allow_remote_clients) or admin_token_configured,
        "auth_token_count": len(auth_records),
        "configured_roles": configured_roles,
        "auth_token_hygiene_healthy": bool(auth_token_hygiene["healthy"]),
        "weak_auth_token_count": int(auth_token_hygiene["weak_count"]),
        "legacy_auth_token_count": int(auth_token_hygiene["legacy_count"]),
        "share_link_secret_healthy": share_link_secret_healthy,
        "share_link_secret_uses_default": bool(share_link_secret_uses_default()),
        "share_link_secret_min_length": int(min_share_link_secret_length),
        "remote_share_ready": (not allow_remote_clients) or share_link_secret_healthy,
        "remote_management_rate_limit_enabled": bool(
            remote_management_rate_limit_enabled
        ),
        "remote_management_rate_limit_window_seconds": int(
            remote_management_rate_limit_window_seconds
        ),
        "remote_management_rate_limit_window_seconds_source": str(
            remote_management_rate_limit_window_seconds_source
        ),
        "remote_management_rate_limit_max_requests": int(
            remote_management_rate_limit_max_requests
        ),
        "remote_management_rate_limit_max_requests_source": str(
            remote_management_rate_limit_max_requests_source
        ),
        "remote_management_rate_limit_scope": "remote-management",
        "remote_management_rate_limit_storage": "memory",
        "remote_management_rate_limit_path_prefixes": [
            str(item)
            for item in remote_management_rate_limit_status.get("path_prefixes", [])
        ],
        "remote_management_rate_limit_response_headers": [
            str(item)
            for item in remote_management_rate_limit_status.get(
                "response_headers", []
            )
        ],
        "remote_management_rate_limit_tracked_principal_count": int(
            remote_management_rate_limit_status.get("tracked_principal_count", 0) or 0
        ),
        "remote_management_rate_limit_active_request_count": int(
            remote_management_rate_limit_status.get("active_request_count", 0) or 0
        ),
        "remote_management_rate_limit_blocked_count": int(
            remote_management_rate_limit_status.get("blocked_count", 0) or 0
        ),
        "remote_management_rate_limit_last_blocked_at": remote_management_rate_limit_status.get(
            "last_blocked_at"
        ),
        "remote_management_rate_limit_next_reset_after_seconds": int(
            remote_management_rate_limit_status.get("next_reset_after_seconds", 0)
            or 0
        ),
        "share_link_ttl_seconds": int(share_link_ttl_seconds),
        "share_link_ttl_hours": round(float(share_link_ttl_seconds) / 3600.0, 2),
        "cors_allow_credentials": cors_allow_credentials,
        "cors_allowed_origins": cors_allowed_origins,
        "request_id_header": "X-Request-ID",
        "process_time_header": "X-Process-Time-Ms",
        "security_audit_storage": "sqlite",
        "security_audit_history_limit": int(security_audit_history_limit),
        "security_audit_history_limit_source": str(security_audit_history_limit_source),
        "security_audit_persisted_count": int(security_audit_persisted_count),
        "security_audit_memory_window_limit": int(security_audit_memory_window_limit),
        "chat_file_limits": chat_file_limits,
        "document_upload_limits": document_upload_limits,
    }


def build_sso_config_payload(
    *,
    provider: str,
    issuer_url: str,
    authorization_endpoint: str = "",
    token_endpoint: str = "",
    jwks_url: str = "",
    client_id: str,
    client_secret: str,
    allowed_domains: str,
    scopes: list[str] | str = (),
    default_role: str = "viewer",
    session_ttl_seconds: int = 28800,
    callback_path: str = "/api/auth/sso/callback",
) -> dict[str, Any]:
    normalized_provider = str(provider or "").strip().lower()
    if not normalized_provider and (
        str(issuer_url or "").strip() or str(client_id or "").strip()
    ):
        normalized_provider = "oidc"
    if normalized_provider in {"", "none", "disabled", "off", "false"}:
        normalized_provider = "none"

    normalized_issuer_url = str(issuer_url or "").strip()
    normalized_authorization_endpoint = str(authorization_endpoint or "").strip()
    normalized_token_endpoint = str(token_endpoint or "").strip()
    normalized_jwks_url = str(jwks_url or "").strip()
    client_id_configured = bool(str(client_id or "").strip())
    client_secret_configured = bool(str(client_secret or "").strip())
    authorization_endpoint_configured = bool(normalized_authorization_endpoint)
    token_endpoint_configured = bool(normalized_token_endpoint)
    jwks_url_configured = bool(normalized_jwks_url)
    enabled = normalized_provider != "none"
    ready = (
        enabled
        and normalized_provider == "oidc"
        and bool(normalized_issuer_url)
        and authorization_endpoint_configured
        and token_endpoint_configured
        and jwks_url_configured
        and client_id_configured
    )
    if not enabled:
        mode = "disabled"
    elif ready:
        mode = "oidc_configured"
    else:
        mode = "incomplete"

    return {
        "enabled": enabled,
        "provider": normalized_provider,
        "issuer_url": normalized_issuer_url,
        "authorization_endpoint": normalized_authorization_endpoint,
        "token_endpoint": normalized_token_endpoint,
        "jwks_url": normalized_jwks_url,
        "authorization_endpoint_configured": authorization_endpoint_configured,
        "token_endpoint_configured": token_endpoint_configured,
        "jwks_url_configured": jwks_url_configured,
        "client_id": str(client_id or "").strip(),
        "client_id_configured": client_id_configured,
        "client_secret_configured": client_secret_configured,
        "allowed_domains": _csv_values(allowed_domains),
        "scopes": _scope_values(scopes),
        "default_role": str(default_role or "viewer").strip().lower(),
        "session_ttl_seconds": int(session_ttl_seconds or 28800),
        "callback_path": str(callback_path or "/api/auth/sso/callback").strip(),
        "ready": ready,
        "mode": mode,
        "claim_mapping": {
            "user_id": "sub",
            "email": "email",
            "display_name": "name",
            "groups": "groups",
        },
    }


def normalize_sso_config_update(
    field: str,
    value: Any,
    *,
    default_auth_role: str = "viewer",
    normalize_auth_role: Callable[..., str],
) -> str:
    normalized = str(value or "").strip()
    if field == "provider":
        normalized = normalized.lower() or "none"
        if normalized not in {"none", "oidc"}:
            raise ValueError("SSO provider must be none or oidc")
    elif field == "default_role":
        normalized = normalize_auth_role(normalized, default=default_auth_role)
    elif field == "session_ttl_seconds":
        try:
            ttl_seconds = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "SSO session TTL must be an integer number of seconds"
            ) from exc
        if ttl_seconds < 300 or ttl_seconds > 7 * 24 * 60 * 60:
            raise ValueError("SSO session TTL must be between 300 and 604800 seconds")
        normalized = str(ttl_seconds)
    return normalized


def sso_callback_url_for_mode(callback_url: str, response_mode: str = "") -> str:
    normalized_callback_url = str(callback_url or "").strip()
    if str(response_mode or "").strip().lower() == "fragment":
        return f"{normalized_callback_url}?response_mode=fragment"
    return normalized_callback_url


def pkce_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(str(verifier).encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def sso_session_token_hash(token: Any) -> str:
    normalized_token = str(token or "").strip()
    return hashlib.sha256(normalized_token.encode("utf-8")).hexdigest()


def share_link_audit_payload(
    record: Any,
    *,
    current_time: float,
    token_preview_func: Callable[[Any], str] = token_preview,
    token_fingerprint_func: Callable[[Any], str] = token_fingerprint,
) -> dict[str, Any]:
    revoked_at = getattr(record, "revoked_at", None)
    expires_at = float(getattr(record, "expires_at", 0) or 0)
    share_token = str(getattr(record, "share_token", "") or "").strip()
    return {
        "resource_type": str(getattr(record, "resource_type", "") or "").strip(),
        "resource_id": str(getattr(record, "resource_id", "") or "").strip(),
        "created_at": float(getattr(record, "created_at", 0) or 0),
        "expires_at": expires_at,
        "revoked_at": float(revoked_at) if revoked_at is not None else None,
        "is_active": revoked_at is None and expires_at > float(current_time),
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
        "share_token_preview": token_preview_func(share_token),
        "share_token_fingerprint": token_fingerprint_func(share_token),
    }


def security_audit_detail_value(details: Any, *names: str) -> str:
    normalized_names = {str(name or "").strip().lower() for name in names}
    for match in re.finditer(
        r"(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>[^ ]*)",
        str(details or ""),
    ):
        key = str(match.group("key") or "").strip().lower()
        if key in normalized_names:
            return str(match.group("value") or "").strip()
    return ""


def security_audit_redacted_details(details: Any) -> str:
    """Keep detail context useful for SIEM while removing obvious secrets."""

    text = sanitize_log_value(details, max_length=512)
    if not text:
        return ""
    sensitive_key_pattern = (
        r"(?i)\b(token|secret|password|passwd|authorization|api[_-]?key|"
        r"client[_-]?secret|state|nonce|code|session[_-]?token)=([^ ]+)"
    )
    text = re.sub(
        sensitive_key_pattern,
        lambda match: f"{match.group(1)}=<redacted>",
        text,
    )
    return re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+",
        "Bearer <redacted>",
        text,
    )


def safe_epoch_seconds(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def security_audit_event_to_payload(record: Any) -> dict[str, Any]:
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


def security_audit_event_org(event: Mapping[str, Any]) -> str:
    return str(event.get("org_id") or "").strip()


def security_audit_event_tenant(event: Mapping[str, Any]) -> str:
    tenant = str(event.get("tenant_id") or "").strip()
    return tenant or security_audit_event_org(event)


def security_audit_siem_event_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    action = sanitize_log_value(event.get("action"), max_length=128)
    result = sanitize_log_value(event.get("result"), max_length=32)
    org_id = security_audit_event_org(event) or security_audit_detail_value(
        event.get("details"), "org_id", "org", "organization_id"
    )
    tenant_id = security_audit_event_tenant(event) or security_audit_detail_value(
        event.get("details"), "tenant_id", "tenant"
    )
    if not tenant_id and org_id:
        tenant_id = org_id
    return {
        "time": float(safe_epoch_seconds(event.get("timestamp")) or 0.0),
        "request_id": sanitize_log_value(event.get("request_id"), max_length=128),
        "action": action,
        "result": result,
        "category": security_audit_category_for_action(action),
        "user_id": sanitize_log_value(event.get("user_id"), max_length=128),
        "user_role": sanitize_log_value(event.get("user_role"), max_length=64),
        "tenant": sanitize_log_value(tenant_id, max_length=128),
        "tenant_id": sanitize_log_value(tenant_id, max_length=128),
        "org": sanitize_log_value(org_id, max_length=128),
        "org_id": sanitize_log_value(org_id, max_length=128),
        "ip": sanitize_log_value(event.get("ip"), max_length=64),
        "auth_mode": sanitize_log_value(event.get("auth_mode"), max_length=32),
        "auth_source": sanitize_log_value(event.get("auth_source"), max_length=64),
        "legal_hold": bool(event.get("legal_hold")),
        "details": security_audit_redacted_details(event.get("details")),
    }


def build_security_audit_siem_export_payload(
    events: list[Mapping[str, Any]],
    *,
    format: str = "json",
    limit: int = 100,
    filters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_format = str(format or "json").strip().lower()
    if normalized_format not in {"json", "ndjson"}:
        normalized_format = "json"
    exported_events = [security_audit_siem_event_payload(event) for event in events]
    content = ""
    if normalized_format == "ndjson":
        content = "\n".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True)
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
        "limit": limit,
        "filters": dict(filters or {}),
    }


def build_security_audit_archive_policy_payload(
    events: list[Mapping[str, Any]],
    *,
    mode: str = "preview",
    retention_days: int = 365,
    current_time: float,
    limit: int = 100,
    history_limit: int = 0,
    legal_hold: bool = False,
) -> dict[str, Any]:
    """Build the archive preview/export envelope from preloaded audit events."""

    normalized_mode = str(mode or "preview").strip().lower()
    if normalized_mode not in {"preview", "export"}:
        normalized_mode = "preview"
    normalized_retention_days = max(0, int(retention_days or 0))
    normalized_history_limit = max(1, int(history_limit or 0))
    normalized_limit = max(1, min(int(limit or 100), normalized_history_limit))
    cutoff_timestamp = (
        float(current_time) - float(normalized_retention_days * 86400)
        if normalized_retention_days > 0
        else None
    )
    normalized_events = [dict(event) for event in events]
    legal_hold_count = sum(
        1 for event in normalized_events if bool(event.get("legal_hold"))
    )
    candidates = [
        event
        for event in normalized_events
        if not bool(event.get("legal_hold"))
        and (
            cutoff_timestamp is None
            or float(safe_epoch_seconds(event.get("timestamp")) or 0.0)
            <= cutoff_timestamp
        )
    ]
    legal_hold_preserved_count = sum(
        1
        for event in normalized_events
        if bool(event.get("legal_hold"))
        and (
            cutoff_timestamp is None
            or float(safe_epoch_seconds(event.get("timestamp")) or 0.0)
            <= cutoff_timestamp
        )
    )
    export_events = (
        [
            security_audit_siem_event_payload(event)
            for event in candidates[:normalized_limit]
        ]
        if normalized_mode == "export"
        else []
    )
    return {
        "mode": normalized_mode,
        "retention_days": normalized_retention_days,
        "cutoff_timestamp": cutoff_timestamp,
        "history_limit": normalized_history_limit,
        "total": len(normalized_events),
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


SECURITY_AUDIT_AGGREGATE_GROUP_BY = (
    "tenant",
    "org",
    "user_id",
    "category",
    "action",
    "result",
)


def _increment_nested_count(
    totals: dict[str, dict[str, int]], dimension: str, value: Any, count: int = 1
) -> None:
    bucket = totals.setdefault(dimension, {})
    key = str(value or "unknown").strip() or "unknown"
    bucket[key] = bucket.get(key, 0) + int(count)


def build_security_audit_aggregate_report_payload(
    events: list[Mapping[str, Any]],
    *,
    limit: int = 0,
    filters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    groups: dict[tuple[str, str, str, str, str, str], int] = {}
    totals: dict[str, dict[str, int]] = {}
    for event in events:
        siem_event = security_audit_siem_event_payload(event)
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
        for dimension in SECURITY_AUDIT_AGGREGATE_GROUP_BY:
            _increment_nested_count(totals, dimension, row[dimension], row["count"])
    return {
        "total": len(events),
        "window_limit": int(limit or 0),
        "group_by": list(SECURITY_AUDIT_AGGREGATE_GROUP_BY),
        "rows": rows,
        "totals": {key: dict(sorted(value.items())) for key, value in totals.items()},
        "filters": dict(filters or {}),
    }


def filter_security_audit_events(
    events: list[Mapping[str, Any]],
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
            event_category = security_audit_category_for_action(item_action)
            if event_category != normalized_category:
                continue
        item_user_id = str(item.get("user_id") or "").strip()
        if normalized_user_id and item_user_id != normalized_user_id:
            continue
        timestamp = safe_epoch_seconds(item.get("timestamp")) or 0.0
        if since is not None and timestamp < since:
            continue
        if until is not None and timestamp > until:
            continue
        filtered.append(dict(item))
    return filtered


def build_sso_login_payload(
    *,
    provider: str,
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
    scopes: list[str] | str = (),
) -> dict[str, Any]:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider != "oidc":
        raise ValueError("SSO_PROVIDER must be oidc")
    normalized_authorization_endpoint = str(authorization_endpoint or "").strip()
    if not normalized_authorization_endpoint:
        raise ValueError("OIDC_AUTHORIZATION_ENDPOINT is required")
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        raise ValueError("OIDC_CLIENT_ID is required")
    normalized_redirect_uri = str(redirect_uri or "").strip()
    if not normalized_redirect_uri:
        raise ValueError("redirect_uri is required")
    normalized_state = str(state or "").strip()
    normalized_nonce = str(nonce or "").strip()
    normalized_code_challenge = str(code_challenge or "").strip()
    if not normalized_state or not normalized_nonce or not normalized_code_challenge:
        raise ValueError("state, nonce, and code_challenge are required")
    scope_values = _string_scopes(scopes)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": normalized_client_id,
            "redirect_uri": normalized_redirect_uri,
            "scope": " ".join(scope_values),
            "state": normalized_state,
            "nonce": normalized_nonce,
            "code_challenge": normalized_code_challenge,
            "code_challenge_method": "S256",
        }
    )
    separator = "&" if "?" in normalized_authorization_endpoint else "?"
    return {
        "authorization_url": f"{normalized_authorization_endpoint}{separator}{query}",
        "state": normalized_state,
        "nonce": normalized_nonce,
        "code_challenge_method": "S256",
        "redirect_uri": normalized_redirect_uri,
        "scopes": scope_values,
    }


def _string_scopes(scopes: list[str] | str) -> list[str]:
    values = _scope_values(scopes)
    normalized = values or ["openid", "email", "profile"]
    if "openid" not in normalized:
        normalized.insert(0, "openid")
    return normalized


def build_role_permission_matrix_payload() -> dict[str, Any]:
    roles = list(RESOURCE_ROLE_RANKS)
    operations = []
    for operation in RESOURCE_PERMISSION_OPERATIONS:
        minimum_role = operation["minimum_role"]
        minimum_rank = RESOURCE_ROLE_RANKS[minimum_role]
        operations.append(
            {
                "operation": operation["operation"],
                "minimum_role": minimum_role,
                "roles": {
                    role: rank >= minimum_rank
                    for role, rank in RESOURCE_ROLE_RANKS.items()
                },
                "description": operation["description"],
            }
        )
    return {
        "roles": roles,
        "operations": operations,
        "role_ranks": dict(RESOURCE_ROLE_RANKS),
        "inheritance_rule": (
            "Organization grants are capped by the user's membership role; "
            "user grants take their explicit role."
        ),
    }


def build_security_audit_action_catalog_payload(
    *, category: str = ""
) -> dict[str, Any]:
    normalized_category = str(category or "").strip().lower()
    actions = [
        dict(action)
        for action in SECURITY_AUDIT_ACTIONS
        if not normalized_category or action["category"] == normalized_category
    ]
    categories = sorted({str(action["category"]) for action in SECURITY_AUDIT_ACTIONS})
    return {
        "actions": actions,
        "total": len(actions),
        "categories": categories,
    }


def security_audit_category_for_action(action: Any) -> str:
    normalized_action = str(action or "").strip()
    action_categories = {
        str(item["action"]): str(item["category"])
        for item in SECURITY_AUDIT_ACTIONS
    }
    return action_categories.get(normalized_action, "uncategorized")


def build_security_audit_summary_payload(
    events: list[Mapping[str, Any]],
    *,
    category: str = "",
    window_limit: int = 0,
) -> dict[str, Any]:
    """Aggregate security audit events without exposing raw details or tokens."""

    action_categories = {
        str(action["action"]): str(action["category"])
        for action in SECURITY_AUDIT_ACTIONS
    }
    known_categories = sorted(set(action_categories.values()))
    normalized_category = str(category or "").strip().lower()
    filtered_events: list[Mapping[str, Any]] = []
    unknown_action_count = 0

    for event in events:
        action = str(event.get("action") or "").strip()
        event_category = action_categories.get(action, "uncategorized")
        if normalized_category and event_category != normalized_category:
            continue
        if event_category == "uncategorized":
            unknown_action_count += 1
        filtered_events.append(event)

    action_counts: dict[str, int] = {}
    result_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for event in filtered_events:
        action = str(event.get("action") or "").strip() or "unknown"
        result = str(event.get("result") or "").strip() or "unknown"
        event_category = action_categories.get(action, "uncategorized")
        action_counts[action] = action_counts.get(action, 0) + 1
        result_counts[result] = result_counts.get(result, 0) + 1
        category_counts[event_category] = category_counts.get(event_category, 0) + 1

    return {
        "category": normalized_category,
        "categories": known_categories,
        "total": len(filtered_events),
        "recent_count": len(filtered_events),
        "window_limit": int(window_limit or len(events)),
        "action_counts": dict(sorted(action_counts.items())),
        "result_counts": dict(sorted(result_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "unknown_action_count": int(unknown_action_count),
    }


def build_auth_token_catalog_payload(
    *,
    default_role: str,
    configured_auth_token_records: Callable[[], list[dict[str, str]]],
    auth_token_hygiene_summary: Callable[[list[dict[str, str]] | None], dict[str, int | bool]],
    auth_token_preview: Callable[[str], str],
    token_fingerprint: Callable[[str], str],
    auth_token_is_weak: Callable[[Any], bool],
    role_rank: Callable[[str], int],
) -> dict[str, Any]:
    auth_records = configured_auth_token_records()
    auth_token_hygiene = auth_token_hygiene_summary(auth_records)
    tokens = [
        {
            "user_id": str(record.get("user_id") or "").strip(),
            "role": str(record.get("role") or "").strip() or default_role,
            "auth_source": str(record.get("auth_source") or "").strip(),
            "token_preview": auth_token_preview(record.get("token") or ""),
            "token_fingerprint": token_fingerprint(record.get("token") or ""),
            "is_legacy": str(record.get("auth_source") or "").strip().startswith("legacy_"),
            "is_weak": auth_token_is_weak(record.get("token") or ""),
        }
        for record in auth_records
    ]
    configured_roles = sorted({item["role"] for item in tokens}, key=role_rank)
    return {
        "tokens": tokens,
        "total": len(tokens),
        "configured_roles": configured_roles,
        "healthy": bool(auth_token_hygiene["healthy"]),
        "weak_count": int(auth_token_hygiene["weak_count"]),
        "legacy_count": int(auth_token_hygiene["legacy_count"]),
    }


__all__ = [
    "AUTH_ROLE_RANKS",
    "hash_secret",
    "token_fingerprint",
    "token_preview",
    "auth_token_preview",
    "normalize_auth_role",
    "role_rank",
    "sanitize_log_value",
    "sanitize_request_path",
    "auth_token_is_weak",
    "ceil_seconds",
    "content_hash",
    "safe_epoch_seconds",
    "auth_capabilities_for_role",
    "build_auth_whoami_payload",
    "build_security_status_payload",
    "build_sso_config_payload",
    "normalize_sso_config_update",
    "sso_callback_url_for_mode",
    "pkce_code_challenge",
    "sso_session_token_hash",
    "share_link_audit_payload",
    "security_audit_detail_value",
    "security_audit_event_org",
    "security_audit_event_tenant",
    "security_audit_event_to_payload",
    "security_audit_redacted_details",
    "security_audit_siem_event_payload",
    "build_security_audit_siem_export_payload",
    "build_security_audit_archive_policy_payload",
    "build_security_audit_aggregate_report_payload",
    "filter_security_audit_events",
    "build_sso_login_payload",
    "build_role_permission_matrix_payload",
    "build_security_audit_action_catalog_payload",
    "security_audit_category_for_action",
    "build_security_audit_summary_payload",
    "build_auth_token_catalog_payload",
]
