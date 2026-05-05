"""Secret-safe persistence helpers for Integrator outbound audit."""

from __future__ import annotations

import os
import re
import threading
from typing import Any

from backend.stores.integrator_outbound_audit_store import (
    SQLiteIntegratorOutboundAuditStore,
)


DEFAULT_INTEGRATOR_OUTBOUND_AUDIT_HISTORY_LIMIT = 1000
MAX_INTEGRATOR_OUTBOUND_AUDIT_QUERY_LIMIT = 500
_REDACTED = "***redacted***"
_REDACTED_URL = "***redacted-url***"
_SECRET_KEYWORDS = (
    "secret",
    "token",
    "password",
    "credential",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "signature",
    "webhook_url",
    "url",
)
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_INLINE_SECRET_PATTERN = re.compile(
    r"(?i)\b(token|secret|password|authorization|api[_-]?key)=((?:Bearer\s+)?[^\s,;&]+)"
)
_store_lock = threading.Lock()
_default_store: SQLiteIntegratorOutboundAuditStore | None = None


def integrator_outbound_audit_history_limit() -> int:
    raw_value = os.getenv("INTEGRATOR_OUTBOUND_AUDIT_HISTORY_LIMIT", "")
    try:
        return max(1, int(raw_value or DEFAULT_INTEGRATOR_OUTBOUND_AUDIT_HISTORY_LIMIT))
    except ValueError:
        return DEFAULT_INTEGRATOR_OUTBOUND_AUDIT_HISTORY_LIMIT


def get_integrator_outbound_audit_store() -> SQLiteIntegratorOutboundAuditStore:
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = SQLiteIntegratorOutboundAuditStore(
                    history_limit=integrator_outbound_audit_history_limit()
                )
    return _default_store


def persist_integrator_outbound_audit_record(
    record: dict[str, Any],
    *,
    store: SQLiteIntegratorOutboundAuditStore | None = None,
) -> dict[str, Any]:
    persisted = (store or get_integrator_outbound_audit_store()).append(
        sanitize_integrator_outbound_audit_record(record)
    )
    return stored_integrator_outbound_audit_record_payload(persisted)


def integrator_outbound_audit_payload(
    *,
    limit: int = 50,
    store: SQLiteIntegratorOutboundAuditStore | None = None,
) -> dict[str, Any]:
    audit_store = store or get_integrator_outbound_audit_store()
    safe_limit = _safe_limit(limit)
    records = [
        stored_integrator_outbound_audit_record_payload(record)
        for record in audit_store.list_recent(limit=safe_limit)
    ]
    return {
        "events": records,
        "total": audit_store.count_events(),
        "limit": safe_limit,
        "retention": {
            "history_limit": audit_store.history_limit,
            "sensitive_fields_redacted": True,
        },
    }


def cleanup_integrator_outbound_audit_payload(
    *,
    keep_latest: int = 0,
    dry_run: bool = False,
    store: SQLiteIntegratorOutboundAuditStore | None = None,
) -> dict[str, Any]:
    audit_store = store or get_integrator_outbound_audit_store()
    safe_keep = max(0, int(keep_latest or 0))
    before_count = audit_store.count_events()
    would_delete_count = max(0, before_count - safe_keep)
    deleted_count = 0 if dry_run else audit_store.trim_to_latest(safe_keep)
    return {
        "dry_run": bool(dry_run),
        "would_delete_count": would_delete_count,
        "deleted_count": deleted_count,
        "remaining_count": audit_store.count_events(),
        "keep_latest": safe_keep,
        "history_limit": audit_store.history_limit,
    }


def stored_integrator_outbound_audit_record_payload(record: Any) -> dict[str, Any]:
    payload = sanitize_integrator_outbound_audit_record(dict(record.record or {}))
    payload.update(
        {
            "id": int(record.id),
            "created_at": str(record.created_at or payload.get("created_at") or ""),
            "timestamp": float(record.timestamp or 0),
        }
    )
    return payload


def sanitize_integrator_outbound_audit_record(value: Any) -> Any:
    return _sanitize_value(value)


def _sanitize_value(value: Any, *, key: str = "") -> Any:
    key_text = str(key or "").lower()
    if _is_secret_key(key_text):
        return _REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, key=key_text) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item, key=key_text) for item in value]
    if isinstance(value, str):
        without_urls = _URL_PATTERN.sub(_REDACTED_URL, value)
        return _INLINE_SECRET_PATTERN.sub(
            lambda match: f"{match.group(1)}={_REDACTED}",
            without_urls,
        )
    return value


def _is_secret_key(key: str) -> bool:
    normalized = str(key or "").replace("-", "_").lower()
    return any(keyword in normalized for keyword in _SECRET_KEYWORDS)


def _safe_limit(limit: int) -> int:
    try:
        value = int(limit or 50)
    except (TypeError, ValueError):
        value = 50
    return max(1, min(value, MAX_INTEGRATOR_OUTBOUND_AUDIT_QUERY_LIMIT))


__all__ = [
    "DEFAULT_INTEGRATOR_OUTBOUND_AUDIT_HISTORY_LIMIT",
    "MAX_INTEGRATOR_OUTBOUND_AUDIT_QUERY_LIMIT",
    "cleanup_integrator_outbound_audit_payload",
    "get_integrator_outbound_audit_store",
    "integrator_outbound_audit_history_limit",
    "integrator_outbound_audit_payload",
    "persist_integrator_outbound_audit_record",
    "sanitize_integrator_outbound_audit_record",
    "stored_integrator_outbound_audit_record_payload",
]
