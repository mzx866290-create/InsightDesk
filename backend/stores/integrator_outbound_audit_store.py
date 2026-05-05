"""Persistent outbound audit store for Integrator webhook execution."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from backend.chat_store import connect_sqlite
from backend.core.storage_runtime import app_database_path


@dataclass(frozen=True)
class IntegratorOutboundAuditStoredRecord:
    id: int
    created_at: str
    timestamp: float
    event: str
    task_id: str
    connector_id: str
    connector_type: str
    status: str
    endpoint_fingerprint: str
    record: dict[str, Any]


class SQLiteIntegratorOutboundAuditStore:
    def __init__(
        self,
        db_path: str | None = None,
        *,
        history_limit: int = 1000,
    ) -> None:
        self.db_path = str(db_path or app_database_path()).strip()
        self.history_limit = max(1, int(history_limit or 1000))
        self._init_db()
        self.prune()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS integrator_outbound_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event TEXT NOT NULL,
                    task_id TEXT DEFAULT '',
                    connector_id TEXT DEFAULT '',
                    connector_type TEXT DEFAULT '',
                    status TEXT DEFAULT '',
                    endpoint_fingerprint TEXT DEFAULT '',
                    record_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_integrator_outbound_audit_recent
                ON integrator_outbound_audit_events(timestamp DESC, id DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_integrator_outbound_audit_connector
                ON integrator_outbound_audit_events(connector_id, timestamp DESC, id DESC)
                """
            )
            conn.commit()

    @staticmethod
    def _from_row(row: tuple[Any, ...] | None) -> IntegratorOutboundAuditStoredRecord | None:
        if row is None:
            return None
        try:
            record = json.loads(str(row[9] or "{}"))
        except json.JSONDecodeError:
            record = {}
        if not isinstance(record, dict):
            record = {}
        return IntegratorOutboundAuditStoredRecord(
            id=int(row[0] or 0),
            created_at=str(row[1] or ""),
            timestamp=float(row[2] or 0),
            event=str(row[3] or ""),
            task_id=str(row[4] or ""),
            connector_id=str(row[5] or ""),
            connector_type=str(row[6] or ""),
            status=str(row[7] or ""),
            endpoint_fingerprint=str(row[8] or ""),
            record=record,
        )

    def append(self, record: dict[str, Any]) -> IntegratorOutboundAuditStoredRecord:
        self._init_db()
        safe_record = dict(record or {})
        connector = safe_record.get("connector") if isinstance(safe_record.get("connector"), dict) else {}
        endpoint = safe_record.get("endpoint") if isinstance(safe_record.get("endpoint"), dict) else {}
        created_at = str(safe_record.get("created_at") or "")
        timestamp = float(safe_record.get("timestamp") or time.time())
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO integrator_outbound_audit_events (
                    created_at,
                    timestamp,
                    event,
                    task_id,
                    connector_id,
                    connector_type,
                    status,
                    endpoint_fingerprint,
                    record_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    timestamp,
                    str(safe_record.get("event") or ""),
                    str(safe_record.get("task_id") or ""),
                    str(connector.get("id") or ""),
                    str(connector.get("type") or ""),
                    str(safe_record.get("status") or ""),
                    str(endpoint.get("fingerprint") or ""),
                    json.dumps(safe_record, ensure_ascii=False, sort_keys=True),
                ),
            )
            row_id = int(cursor.lastrowid or 0)
            conn.commit()
        self.prune()
        record = self.get(row_id)
        if record is None:
            raise RuntimeError("Failed to persist integrator outbound audit event")
        return record

    def get(self, row_id: int) -> IntegratorOutboundAuditStoredRecord | None:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT id, created_at, timestamp, event, task_id, connector_id,
                       connector_type, status, endpoint_fingerprint, record_json
                FROM integrator_outbound_audit_events
                WHERE id = ?
                """,
                (int(row_id),),
            ).fetchone()
        return self._from_row(row)

    def list_recent(self, *, limit: int = 50) -> list[IntegratorOutboundAuditStoredRecord]:
        self._init_db()
        normalized_limit = max(1, min(int(limit or 50), self.history_limit))
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, timestamp, event, task_id, connector_id,
                       connector_type, status, endpoint_fingerprint, record_json
                FROM integrator_outbound_audit_events
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()
        return [
            record
            for record in (self._from_row(row) for row in rows)
            if record is not None
        ]

    def count_events(self) -> int:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM integrator_outbound_audit_events"
            ).fetchone()
        return int(row[0] or 0) if row is not None else 0

    def trim_to_latest(self, keep_latest: int = 0) -> int:
        self._init_db()
        normalized_keep = max(0, int(keep_latest or 0))
        before_count = self.count_events()
        with connect_sqlite(self.db_path) as conn:
            if normalized_keep <= 0:
                conn.execute("DELETE FROM integrator_outbound_audit_events")
            else:
                conn.execute(
                    """
                    DELETE FROM integrator_outbound_audit_events
                    WHERE id NOT IN (
                        SELECT id
                        FROM integrator_outbound_audit_events
                        ORDER BY timestamp DESC, id DESC
                        LIMIT ?
                    )
                    """,
                    (normalized_keep,),
                )
            conn.commit()
        after_count = self.count_events()
        return max(0, before_count - after_count)

    def prune(self) -> None:
        self.trim_to_latest(self.history_limit)
