"""Backend store exports with lazy imports.

The ARQ ops worker imports only the task store. Keeping the package initializer
lazy prevents that drill path from loading the heavier chat/config stores.
"""

from __future__ import annotations

from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "SQLiteAppConfigStore": ("backend.stores.config_store", "SQLiteAppConfigStore"),
    "StoredConfigValue": ("backend.stores.config_store", "StoredConfigValue"),
    "SecurityAuditEventStoredRecord": (
        "backend.stores.security_audit_store",
        "SecurityAuditEventStoredRecord",
    ),
    "SQLiteSecurityAuditStore": (
        "backend.stores.security_audit_store",
        "SQLiteSecurityAuditStore",
    ),
    "ShareLinkRecord": ("backend.stores.share_link_store", "ShareLinkRecord"),
    "SQLiteShareLinkStore": ("backend.stores.share_link_store", "SQLiteShareLinkStore"),
    "AttachmentPromotionRecord": (
        "backend.stores.task_store",
        "AttachmentPromotionRecord",
    ),
    "RESTART_FAILURE_MESSAGE": ("backend.stores.task_store", "RESTART_FAILURE_MESSAGE"),
    "SQLiteTaskStore": ("backend.stores.task_store", "SQLiteTaskStore"),
    "TaskRecord": ("backend.stores.task_store", "TaskRecord"),
    "TaskStatus": ("backend.stores.task_store", "TaskStatus"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
