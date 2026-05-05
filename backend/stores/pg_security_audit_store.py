"""PostgreSQL security audit event store adapter."""

from __future__ import annotations

from typing import Any, Callable

from backend.stores.pg_base import PostgresStoreMixin
from backend.stores.security_audit_store import (
    SecurityAuditEventStoredRecord,
    SQLiteSecurityAuditStore,
    _detail_field,
)


class PostgresSecurityAuditStore(PostgresStoreMixin, SQLiteSecurityAuditStore):
    """PostgreSQL implementation for security audit events."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        history_limit: int = 2000,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        PostgresStoreMixin.__init__(self, dsn, connection_factory=connection_factory)
        self.db_path = self.dsn
        self.history_limit = max(1, int(history_limit or 2000))
        self._init_db()
        self.prune()

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS security_audit_events (
                        id BIGSERIAL PRIMARY KEY,
                        timestamp DOUBLE PRECISION NOT NULL,
                        request_id TEXT DEFAULT '',
                        action TEXT NOT NULL,
                        result TEXT NOT NULL,
                        ip TEXT DEFAULT '',
                        is_local INTEGER NOT NULL DEFAULT 0,
                        auth_mode TEXT DEFAULT '',
                        auth_source TEXT DEFAULT '',
                        user_id TEXT DEFAULT '',
                        user_role TEXT DEFAULT '',
                        details TEXT DEFAULT '',
                        tenant_id TEXT DEFAULT '',
                        org_id TEXT DEFAULT '',
                        legal_hold INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_security_audit_timestamp
                    ON security_audit_events(timestamp DESC, id DESC)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_security_audit_action_result
                    ON security_audit_events(action, result, timestamp DESC, id DESC)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_security_audit_tenant_org
                    ON security_audit_events(tenant_id, org_id, timestamp DESC, id DESC)
                    """
                )
            conn.commit()

    def _record_from_row(self, row: Any | None) -> SecurityAuditEventStoredRecord | None:
        if row is None:
            return None
        return SecurityAuditEventStoredRecord(
            timestamp=float(self._row_value(row, 0, "timestamp") or 0),
            request_id=str(self._row_value(row, 1, "request_id") or ""),
            action=str(self._row_value(row, 2, "action") or ""),
            result=str(self._row_value(row, 3, "result") or ""),
            ip=str(self._row_value(row, 4, "ip") or ""),
            is_local=bool(self._row_value(row, 5, "is_local")),
            auth_mode=str(self._row_value(row, 6, "auth_mode") or ""),
            auth_source=str(self._row_value(row, 7, "auth_source") or ""),
            user_id=str(self._row_value(row, 8, "user_id") or ""),
            user_role=str(self._row_value(row, 9, "user_role") or ""),
            details=str(self._row_value(row, 10, "details") or ""),
            tenant_id=str(self._row_value(row, 11, "tenant_id") or ""),
            org_id=str(self._row_value(row, 12, "org_id") or ""),
            legal_hold=bool(self._row_value(row, 13, "legal_hold")),
        )

    def append(self, event: dict[str, Any]) -> SecurityAuditEventStoredRecord:
        self._init_db()
        details = str(event.get("details") or "")
        org_id = str(event.get("org_id") or "").strip() or _detail_field(
            details, "org_id", "org", "organization_id"
        )
        tenant_id = str(event.get("tenant_id") or "").strip() or _detail_field(
            details, "tenant_id", "tenant"
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO security_audit_events (
                        timestamp, request_id, action, result, ip, is_local,
                        auth_mode, auth_source, user_id, user_role, details,
                        tenant_id, org_id, legal_hold
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        float(event.get("timestamp", 0) or 0),
                        str(event.get("request_id") or ""),
                        str(event.get("action") or ""),
                        str(event.get("result") or ""),
                        str(event.get("ip") or ""),
                        1 if bool(event.get("is_local")) else 0,
                        str(event.get("auth_mode") or ""),
                        str(event.get("auth_source") or ""),
                        str(event.get("user_id") or ""),
                        str(event.get("user_role") or ""),
                        details,
                        tenant_id,
                        org_id,
                        1 if bool(event.get("legal_hold")) else 0,
                    ),
                )
            conn.commit()
        self.prune()
        records = self.list_events(limit=1)
        if not records:
            raise RuntimeError("Failed to persist security audit event")
        return records[-1]

    def _filter_clauses(self, *, action: str = "", result: str = "") -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        normalized_action = str(action or "").strip()
        normalized_result = str(result or "").strip()
        if normalized_action:
            clauses.append("action = %s")
            params.append(normalized_action)
        if normalized_result:
            clauses.append("result = %s")
            params.append(normalized_result)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def list_events(
        self,
        *,
        limit: int = 50,
        action: str = "",
        result: str = "",
    ) -> list[SecurityAuditEventStoredRecord]:
        self._init_db()
        normalized_limit = max(1, min(int(limit or 50), self.history_limit))
        where_sql, params = self._filter_clauses(action=action, result=result)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        timestamp, request_id, action, result, ip, is_local,
                        auth_mode, auth_source, user_id, user_role, details,
                        tenant_id, org_id, legal_hold
                    FROM security_audit_events
                    {where_sql}
                    ORDER BY timestamp DESC, id DESC
                    LIMIT %s
                    """,
                    (*params, normalized_limit),
                )
                rows = cursor.fetchall()
        rows.reverse()
        return [
            record
            for row in rows
            if (record := self._record_from_row(row)) is not None
        ]

    def count_events(self, *, action: str = "", result: str = "") -> int:
        self._init_db()
        where_sql, params = self._filter_clauses(action=action, result=result)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(1) FROM security_audit_events {where_sql}",
                    tuple(params),
                )
                row = cursor.fetchone()
        return int(self._row_value(row, 0, "count") if row else 0)

    def count_legal_hold_events(self) -> int:
        self._init_db()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(1) FROM security_audit_events WHERE legal_hold = 1"
                )
                row = cursor.fetchone()
        return int(self._row_value(row, 0, "count") if row else 0)

    def set_legal_hold(self, request_id: str, *, legal_hold: bool = True) -> int:
        self._init_db()
        normalized_request_id = str(request_id or "").strip()
        if not normalized_request_id:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE security_audit_events
                    SET legal_hold = %s
                    WHERE request_id = %s
                    """,
                    (1 if legal_hold else 0, normalized_request_id),
                )
                updated = int(cursor.rowcount or 0)
            conn.commit()
        return updated

    def trim_to_latest(self, keep_latest: int = 0) -> int:
        self._init_db()
        normalized_keep = max(0, int(keep_latest or 0))
        before_count = self.count_events()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if normalized_keep <= 0:
                    cursor.execute(
                        "DELETE FROM security_audit_events WHERE legal_hold = 0"
                    )
                else:
                    cursor.execute(
                        """
                        DELETE FROM security_audit_events
                        WHERE legal_hold = 0
                        AND id NOT IN (
                            SELECT id
                            FROM security_audit_events
                            ORDER BY timestamp DESC, id DESC
                            LIMIT %s
                        )
                        """,
                        (normalized_keep,),
                    )
            conn.commit()
        after_count = self.count_events()
        return max(0, int(before_count) - int(after_count))

    def prune(self) -> None:
        self.trim_to_latest(self.history_limit)
