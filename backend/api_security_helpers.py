from __future__ import annotations

import logging
from typing import Any, Callable, Mapping


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
