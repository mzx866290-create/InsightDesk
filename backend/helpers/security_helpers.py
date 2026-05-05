from __future__ import annotations

"""Security helper utilities."""

import logging
from typing import Any, Callable, Mapping
from urllib.parse import urlencode


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
    "auth_capabilities_for_role",
    "build_auth_whoami_payload",
    "build_security_status_payload",
    "build_sso_config_payload",
    "build_sso_login_payload",
    "build_role_permission_matrix_payload",
    "build_security_audit_action_catalog_payload",
    "security_audit_category_for_action",
    "build_security_audit_summary_payload",
    "build_auth_token_catalog_payload",
]
