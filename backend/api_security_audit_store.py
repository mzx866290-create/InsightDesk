"""Compatibility re-export for ``backend.stores.security_audit_store``."""

from backend.stores.security_audit_store import (
    SecurityAuditEventStoredRecord,
    SQLiteSecurityAuditStore,
)

__all__ = [
    "SecurityAuditEventStoredRecord",
    "SQLiteSecurityAuditStore",
]
