"""PostgreSQL artifact store adapter."""

from __future__ import annotations

import json
from typing import Any, Callable

from backend.artifact_service import (
    ArtifactRecord,
    SQLiteArtifactStore,
    _normalize_optional_text,
    _normalize_text,
    _now_timestamp,
)
from backend.stores.pg_base import PostgresStoreMixin


class PostgresArtifactStore(PostgresStoreMixin, SQLiteArtifactStore):
    """PostgreSQL implementation for generated report/deck artifacts."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        PostgresStoreMixin.__init__(self, dsn, connection_factory=connection_factory)
        self.db_path = self.dsn
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS artifacts (
                        artifact_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        artifact_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL,
                        linked_resource_type TEXT,
                        linked_resource_id TEXT,
                        content_json TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_artifacts_session
                    ON artifacts(session_id, updated_at DESC, created_at DESC)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_artifacts_linked_resource
                    ON artifacts(linked_resource_type, linked_resource_id, updated_at DESC)
                    """
                )
            conn.commit()

    def save(self, artifact: ArtifactRecord) -> ArtifactRecord:
        now = _now_timestamp()
        created_at = float(getattr(artifact, "created_at", now) or now)
        artifact.updated_at = now
        payload = json.dumps(artifact.content, ensure_ascii=False)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO artifacts (
                        artifact_id, session_id, artifact_type, title, status,
                        linked_resource_type, linked_resource_id, content_json,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(artifact_id) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        artifact_type = EXCLUDED.artifact_type,
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        linked_resource_type = EXCLUDED.linked_resource_type,
                        linked_resource_id = EXCLUDED.linked_resource_id,
                        content_json = EXCLUDED.content_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        artifact.artifact_id,
                        artifact.session_id,
                        artifact.artifact_type,
                        artifact.title,
                        artifact.status,
                        artifact.linked_resource_type,
                        artifact.linked_resource_id,
                        payload,
                        created_at,
                        now,
                    ),
                )
            conn.commit()
        artifact.created_at = created_at
        artifact.updated_at = now
        return artifact

    def _from_row(self, row: Any) -> ArtifactRecord:
        if not row:
            raise KeyError("")
        return ArtifactRecord(
            artifact_id=str(self._row_value(row, 0, "artifact_id") or ""),
            session_id=str(self._row_value(row, 1, "session_id") or ""),
            artifact_type=str(self._row_value(row, 2, "artifact_type") or ""),
            title=str(self._row_value(row, 3, "title") or ""),
            status=str(self._row_value(row, 4, "status") or "") or "ready",
            linked_resource_type=_normalize_optional_text(
                self._row_value(row, 5, "linked_resource_type")
            ),
            linked_resource_id=_normalize_optional_text(
                self._row_value(row, 6, "linked_resource_id")
            ),
            content=json.loads(str(self._row_value(row, 7, "content_json") or "{}")),
            created_at=float(self._row_value(row, 8, "created_at") or 0),
            updated_at=float(self._row_value(row, 9, "updated_at") or 0),
        )

    def get(self, artifact_id: str) -> ArtifactRecord:
        normalized_artifact_id = str(artifact_id or "").strip()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT artifact_id, session_id, artifact_type, title, status,
                           linked_resource_type, linked_resource_id, content_json,
                           created_at, updated_at
                    FROM artifacts
                    WHERE artifact_id = %s
                    """,
                    (normalized_artifact_id,),
                )
                row = cursor.fetchone()
        if not row:
            raise KeyError(normalized_artifact_id)
        return self._from_row(row)

    def list_recent(
        self,
        *,
        limit: int = 100,
        artifact_type: str = "",
    ) -> list[ArtifactRecord]:
        safe_limit = max(1, min(500, int(limit or 100)))
        normalized_artifact_type = _normalize_text(artifact_type)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if normalized_artifact_type:
                    cursor.execute(
                        """
                        SELECT artifact_id
                        FROM artifacts
                        WHERE artifact_type = %s
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT %s
                        """,
                        (normalized_artifact_type, safe_limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT artifact_id
                        FROM artifacts
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT %s
                        """,
                        (safe_limit,),
                    )
                rows = cursor.fetchall()
        return [self.get(str(self._row_value(row, 0, "artifact_id") or "")) for row in rows]

    def list_by_session(
        self,
        session_id: str,
        *,
        artifact_type: str = "",
    ) -> list[ArtifactRecord]:
        normalized_session_id = _normalize_text(session_id)
        if not normalized_session_id:
            return []
        normalized_artifact_type = _normalize_text(artifact_type)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if normalized_artifact_type:
                    cursor.execute(
                        """
                        SELECT artifact_id
                        FROM artifacts
                        WHERE session_id = %s AND artifact_type = %s
                        ORDER BY updated_at DESC, created_at DESC
                        """,
                        (normalized_session_id, normalized_artifact_type),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT artifact_id
                        FROM artifacts
                        WHERE session_id = %s
                        ORDER BY updated_at DESC, created_at DESC
                        """,
                        (normalized_session_id,),
                    )
                rows = cursor.fetchall()
        return [self.get(str(self._row_value(row, 0, "artifact_id") or "")) for row in rows]

    def list_by_linked_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> list[ArtifactRecord]:
        normalized_resource_type = _normalize_text(resource_type)
        normalized_resource_id = _normalize_text(resource_id)
        if not normalized_resource_type or not normalized_resource_id:
            return []
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT artifact_id
                    FROM artifacts
                    WHERE linked_resource_type = %s AND linked_resource_id = %s
                    ORDER BY updated_at DESC, created_at DESC
                    """,
                    (normalized_resource_type, normalized_resource_id),
                )
                rows = cursor.fetchall()
        return [self.get(str(self._row_value(row, 0, "artifact_id") or "")) for row in rows]

    def delete_by_session(self, session_id: str) -> int:
        normalized_session_id = _normalize_text(session_id)
        if not normalized_session_id:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM artifacts WHERE session_id = %s",
                    (normalized_session_id,),
                )
                deleted = int(cursor.rowcount or 0)
            conn.commit()
        return deleted
