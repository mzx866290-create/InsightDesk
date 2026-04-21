from dataclasses import dataclass
from typing import Any

from backend.chat_store import connect_sqlite


@dataclass
class SecurityAuditEventStoredRecord:
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


class SQLiteSecurityAuditStore:
    def __init__(
        self,
        db_path: str = "./chat_history.db",
        *,
        history_limit: int = 2000,
    ):
        self.db_path = db_path
        self.history_limit = max(1, int(history_limit or 2000))
        self._init_db()
        self.prune()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS security_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    request_id TEXT DEFAULT '',
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    ip TEXT DEFAULT '',
                    is_local INTEGER NOT NULL DEFAULT 0,
                    auth_mode TEXT DEFAULT '',
                    auth_source TEXT DEFAULT '',
                    user_id TEXT DEFAULT '',
                    user_role TEXT DEFAULT '',
                    details TEXT DEFAULT ''
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
            conn.commit()

    @staticmethod
    def _from_row(row: tuple[Any, ...] | None) -> SecurityAuditEventStoredRecord | None:
        if row is None:
            return None
        return SecurityAuditEventStoredRecord(
            timestamp=float(row[0] or 0),
            request_id=str(row[1] or ""),
            action=str(row[2] or ""),
            result=str(row[3] or ""),
            ip=str(row[4] or ""),
            is_local=bool(row[5]),
            auth_mode=str(row[6] or ""),
            auth_source=str(row[7] or ""),
            user_id=str(row[8] or ""),
            user_role=str(row[9] or ""),
            details=str(row[10] or ""),
        )

    def append(self, event: dict[str, Any]) -> SecurityAuditEventStoredRecord:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO security_audit_events (
                    timestamp,
                    request_id,
                    action,
                    result,
                    ip,
                    is_local,
                    auth_mode,
                    auth_source,
                    user_id,
                    user_role,
                    details
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    str(event.get("details") or ""),
                ),
            )
            conn.commit()
        self.prune()
        records = self.list_events(limit=1)
        if not records:
            raise RuntimeError("Failed to persist security audit event")
        return records[-1]

    def list_events(
        self,
        *,
        limit: int = 50,
        action: str = "",
        result: str = "",
    ) -> list[SecurityAuditEventStoredRecord]:
        self._init_db()
        normalized_limit = max(1, min(int(limit or 50), self.history_limit))
        normalized_action = str(action or "").strip()
        normalized_result = str(result or "").strip()
        clauses: list[str] = []
        params: list[Any] = []

        if normalized_action:
            clauses.append("action = ?")
            params.append(normalized_action)
        if normalized_result:
            clauses.append("result = ?")
            params.append(normalized_result)

        where_clause = ""
        if clauses:
            where_clause = "WHERE " + " AND ".join(clauses)

        query = f"""
            SELECT
                timestamp,
                request_id,
                action,
                result,
                ip,
                is_local,
                auth_mode,
                auth_source,
                user_id,
                user_role,
                details
            FROM security_audit_events
            {where_clause}
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """
        params.append(normalized_limit)
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        rows.reverse()
        return [record for record in (self._from_row(row) for row in rows) if record is not None]

    def count_events(
        self,
        *,
        action: str = "",
        result: str = "",
    ) -> int:
        self._init_db()
        normalized_action = str(action or "").strip()
        normalized_result = str(result or "").strip()
        clauses: list[str] = []
        params: list[Any] = []

        if normalized_action:
            clauses.append("action = ?")
            params.append(normalized_action)
        if normalized_result:
            clauses.append("result = ?")
            params.append(normalized_result)

        where_clause = ""
        if clauses:
            where_clause = "WHERE " + " AND ".join(clauses)

        query = f"""
            SELECT COUNT(1)
            FROM security_audit_events
            {where_clause}
        """
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        return int(row[0] or 0) if row is not None else 0

    def trim_to_latest(self, keep_latest: int = 0) -> int:
        self._init_db()
        normalized_keep = max(0, int(keep_latest or 0))
        before_count = self.count_events()
        with connect_sqlite(self.db_path) as conn:
            if normalized_keep <= 0:
                conn.execute("DELETE FROM security_audit_events")
            else:
                conn.execute(
                    """
                    DELETE FROM security_audit_events
                    WHERE id NOT IN (
                        SELECT id
                        FROM security_audit_events
                        ORDER BY timestamp DESC, id DESC
                        LIMIT ?
                    )
                    """,
                    (normalized_keep,),
                )
            conn.commit()
        after_count = self.count_events()
        return max(0, int(before_count) - int(after_count))

    def prune(self) -> None:
        self.trim_to_latest(self.history_limit)
