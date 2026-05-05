"""Share link persistence store."""

import time
from dataclasses import dataclass
from typing import Any, Optional

from backend.chat_store import connect_sqlite
from backend.core.storage_runtime import app_database_path


@dataclass
class ShareLinkRecord:
    share_token: str
    resource_type: str
    resource_id: str
    created_at: float
    expires_at: float
    revoked_at: Optional[float] = None
    created_by_ip: str = ""
    created_user_agent: str = ""
    access_count: int = 0
    last_accessed_at: Optional[float] = None
    last_accessed_ip: str = ""
    last_accessed_user_agent: str = ""


class SQLiteShareLinkStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or app_database_path()).strip()
        self._init_db()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS share_links (
                    share_token TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    revoked_at REAL,
                    created_by_ip TEXT DEFAULT '',
                    created_user_agent TEXT DEFAULT '',
                    access_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed_at REAL,
                    last_accessed_ip TEXT DEFAULT '',
                    last_accessed_user_agent TEXT DEFAULT ''
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_share_links_resource
                ON share_links(resource_type, resource_id, created_at DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_share_links_expires
                ON share_links(expires_at)
                """
            )
            conn.commit()

    @staticmethod
    def _from_row(row: tuple[Any, ...] | None) -> ShareLinkRecord | None:
        if row is None:
            return None
        return ShareLinkRecord(
            share_token=str(row[0] or ""),
            resource_type=str(row[1] or ""),
            resource_id=str(row[2] or ""),
            created_at=float(row[3] or 0),
            expires_at=float(row[4] or 0),
            revoked_at=float(row[5]) if row[5] is not None else None,
            created_by_ip=str(row[6] or ""),
            created_user_agent=str(row[7] or ""),
            access_count=int(row[8] or 0),
            last_accessed_at=float(row[9]) if row[9] is not None else None,
            last_accessed_ip=str(row[10] or ""),
            last_accessed_user_agent=str(row[11] or ""),
        )

    def upsert(
        self,
        *,
        share_token: str,
        resource_type: str,
        resource_id: str,
        expires_at: float,
        created_by_ip: str = "",
        created_user_agent: str = "",
    ) -> ShareLinkRecord:
        self._init_db()
        now = time.time()
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO share_links (
                    share_token,
                    resource_type,
                    resource_id,
                    created_at,
                    expires_at,
                    revoked_at,
                    created_by_ip,
                    created_user_agent,
                    access_count,
                    last_accessed_at,
                    last_accessed_ip,
                    last_accessed_user_agent
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?, 0, NULL, '', '')
                ON CONFLICT(share_token) DO UPDATE SET
                    resource_type = excluded.resource_type,
                    resource_id = excluded.resource_id,
                    expires_at = excluded.expires_at,
                    revoked_at = NULL,
                    created_by_ip = excluded.created_by_ip,
                    created_user_agent = excluded.created_user_agent
                """,
                (
                    share_token,
                    resource_type,
                    resource_id,
                    now,
                    float(expires_at),
                    created_by_ip,
                    created_user_agent,
                ),
            )
            conn.commit()
        record = self.get(share_token)
        if record is None:
            raise RuntimeError("Failed to persist share link")
        return record

    def get(self, share_token: str) -> ShareLinkRecord | None:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    share_token,
                    resource_type,
                    resource_id,
                    created_at,
                    expires_at,
                    revoked_at,
                    created_by_ip,
                    created_user_agent,
                    access_count,
                    last_accessed_at,
                    last_accessed_ip,
                    last_accessed_user_agent
                FROM share_links
                WHERE share_token = ?
                """,
                (str(share_token or "").strip(),),
            ).fetchone()
        return self._from_row(row)

    def get_active(
        self, share_token: str, *, now: Optional[float] = None
    ) -> ShareLinkRecord | None:
        record = self.get(share_token)
        if record is None:
            return None
        current_time = time.time() if now is None else float(now)
        if record.revoked_at is not None:
            return None
        if record.expires_at <= current_time:
            return None
        return record

    def list_links(
        self,
        *,
        resource_type: str = "",
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ShareLinkRecord]:
        self._init_db()
        normalized_resource_type = str(resource_type or "").strip()
        normalized_limit = max(1, min(int(limit or 100), 500))
        normalized_offset = max(0, int(offset or 0))

        clauses: list[str] = []
        params: list[Any] = []

        if normalized_resource_type:
            clauses.append("resource_type = ?")
            params.append(normalized_resource_type)
        if active_only:
            clauses.append("revoked_at IS NULL")
            clauses.append("expires_at > ?")
            params.append(time.time())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT
                    share_token,
                    resource_type,
                    resource_id,
                    created_at,
                    expires_at,
                    revoked_at,
                    created_by_ip,
                    created_user_agent,
                    access_count,
                    last_accessed_at,
                    last_accessed_ip,
                    last_accessed_user_agent
                FROM share_links
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, normalized_limit, normalized_offset),
            ).fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def revoke(self, share_token: str) -> bool:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE share_links
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE share_token = ?
                """,
                (time.time(), str(share_token or "").strip()),
            )
            conn.commit()
            return int(cursor.rowcount or 0) > 0

    def delete_for_resource(self, resource_type: str, resource_id: str) -> int:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM share_links
                WHERE resource_type = ? AND resource_id = ?
                """,
                (str(resource_type or "").strip(), str(resource_id or "").strip()),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def record_access(
        self,
        share_token: str,
        *,
        accessed_ip: str = "",
        accessed_user_agent: str = "",
    ) -> None:
        self._init_db()
        now = time.time()
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                UPDATE share_links
                SET access_count = COALESCE(access_count, 0) + 1,
                    last_accessed_at = ?,
                    last_accessed_ip = ?,
                    last_accessed_user_agent = ?
                WHERE share_token = ?
                """,
                (
                    now,
                    str(accessed_ip or ""),
                    str(accessed_user_agent or ""),
                    str(share_token or "").strip(),
                ),
            )
            conn.commit()


__all__ = [
    "ShareLinkRecord",
    "SQLiteShareLinkStore",
]
