"""PostgreSQL task store adapter."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from backend.stores.pg_base import PostgresStoreMixin
from backend.stores.task_store import (
    AttachmentPromotionRecord,
    RESTART_FAILURE_MESSAGE,
    SQLiteTaskStore,
    TaskRecord,
    TaskStatus,
    _fail_incomplete_on_start_from_env,
)


class PostgresTaskStore(PostgresStoreMixin, SQLiteTaskStore):
    """PostgreSQL implementation for persisted task records."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        history_limit: int = 200,
        ttl_seconds: int = 6 * 60 * 60,
        fail_incomplete_on_start: bool | None = None,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        PostgresStoreMixin.__init__(self, dsn, connection_factory=connection_factory)
        self.db_path = self.dsn
        self.history_limit = int(history_limit)
        self.ttl_seconds = int(ttl_seconds)
        self.fail_incomplete_on_start = (
            _fail_incomplete_on_start_from_env()
            if fail_incomplete_on_start is None
            else bool(fail_incomplete_on_start)
        )
        self._init_db()
        if self.fail_incomplete_on_start:
            self._fail_incomplete_tasks()
        self.prune()

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        task_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        params_json TEXT NOT NULL,
                        session_id TEXT,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL,
                        result TEXT,
                        error TEXT,
                        progress INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC)")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at DESC, created_at DESC)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_status_updated ON tasks(status, updated_at DESC)"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attachment_promotions (
                        attachment_id TEXT NOT NULL,
                        vector_store_path TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        attachment_name TEXT,
                        session_id TEXT,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL,
                        result TEXT,
                        error TEXT,
                        PRIMARY KEY (attachment_id, vector_store_path)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_attachment_promotions_task ON attachment_promotions(task_id)"
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_attachment_promotions_status_updated
                    ON attachment_promotions(status, updated_at DESC, created_at DESC)
                    """
                )
            conn.commit()

    def _save_attachment_promotion_for_task(self, cursor: Any, record: TaskRecord) -> None:
        if record.task_type != "promote_attachment_to_kb":
            return
        attachment_id = str(record.params.get("attachment_id") or "").strip()
        vector_store_path = str(record.params.get("vector_store_path") or "").strip()
        attachment_name = str(record.params.get("attachment_name") or "").strip()
        if not attachment_id or not vector_store_path:
            return
        cursor.execute(
            """
            SELECT created_at
            FROM attachment_promotions
            WHERE attachment_id = %s AND vector_store_path = %s
            """,
            (attachment_id, vector_store_path),
        )
        existing_row = cursor.fetchone()
        created_at = (
            float(self._row_value(existing_row, 0, "created_at"))
            if existing_row and self._row_value(existing_row, 0, "created_at") is not None
            else record.created_at
        )
        cursor.execute(
            """
            INSERT INTO attachment_promotions (
                attachment_id, vector_store_path, task_id, status,
                attachment_name, session_id, created_at, updated_at, result, error
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(attachment_id, vector_store_path) DO UPDATE SET
                task_id = EXCLUDED.task_id,
                status = EXCLUDED.status,
                attachment_name = EXCLUDED.attachment_name,
                session_id = EXCLUDED.session_id,
                updated_at = EXCLUDED.updated_at,
                result = EXCLUDED.result,
                error = EXCLUDED.error
            """,
            (
                attachment_id,
                vector_store_path,
                record.task_id,
                record.status.value,
                attachment_name,
                record.session_id,
                created_at,
                record.updated_at,
                record.result,
                record.error,
            ),
        )

    def save(self, record: TaskRecord) -> TaskRecord:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tasks (
                        task_id, task_type, status, params_json, session_id,
                        created_at, updated_at, result, error, progress
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(task_id) DO UPDATE SET
                        task_type = EXCLUDED.task_type,
                        status = EXCLUDED.status,
                        params_json = EXCLUDED.params_json,
                        session_id = EXCLUDED.session_id,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        result = EXCLUDED.result,
                        error = EXCLUDED.error,
                        progress = EXCLUDED.progress
                    """,
                    (
                        record.task_id,
                        record.task_type,
                        record.status.value,
                        json.dumps(record.params, ensure_ascii=False),
                        record.session_id,
                        record.created_at,
                        record.updated_at,
                        record.result,
                        record.error,
                        int(record.progress),
                    ),
                )
                self._save_attachment_promotion_for_task(cursor, record)
            conn.commit()
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id, task_type, status, params_json, session_id,
                           created_at, updated_at, result, error, progress
                    FROM tasks
                    WHERE task_id = %s
                    """,
                    (task_id,),
                )
                row = cursor.fetchone()
        return self._from_row(row)

    def list_recent(self, limit: int = 20) -> list[TaskRecord]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id, task_type, status, params_json, session_id,
                           created_at, updated_at, result, error, progress
                    FROM tasks
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT %s
                    """,
                    (max(1, int(limit)),),
                )
                rows = cursor.fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def _promotion_from_row(self, row: Any) -> AttachmentPromotionRecord | None:
        return SQLiteTaskStore._promotion_from_row(row)

    def get_attachment_promotion(
        self,
        attachment_id: str,
        vector_store_path: str,
    ) -> AttachmentPromotionRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT attachment_id, vector_store_path, task_id, status,
                           attachment_name, session_id, created_at, updated_at, result, error
                    FROM attachment_promotions
                    WHERE attachment_id = %s AND vector_store_path = %s
                    """,
                    (attachment_id, vector_store_path),
                )
                row = cursor.fetchone()
        return self._promotion_from_row(row)

    def _fail_incomplete_tasks(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                now = time.time()
                cursor.execute(
                    """
                    UPDATE tasks
                    SET status = %s,
                        updated_at = %s,
                        error = %s,
                        progress = CASE WHEN progress >= 100 THEN progress ELSE 0 END
                    WHERE status IN (%s, %s)
                    """,
                    (
                        TaskStatus.FAILED.value,
                        now,
                        RESTART_FAILURE_MESSAGE,
                        TaskStatus.PENDING.value,
                        TaskStatus.RUNNING.value,
                    ),
                )
            conn.commit()

    def delete_for_session(self, session_id: str) -> dict[str, int]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return {"tasks": 0, "attachment_promotions": 0}

        deleted_task_records: list[TaskRecord] = []
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id, task_type, status, params_json, session_id,
                           created_at, updated_at, result, error, progress
                    FROM tasks
                    WHERE session_id = %s
                    """,
                    (normalized_session_id,),
                )
                deleted_task_records = [
                    record
                    for row in cursor.fetchall()
                    if (record := self._from_row(row)) is not None
                ]

                cursor.execute(
                    "DELETE FROM tasks WHERE session_id = %s",
                    (normalized_session_id,),
                )
                deleted_tasks = int(cursor.rowcount or 0)

                cursor.execute(
                    "DELETE FROM attachment_promotions WHERE session_id = %s",
                    (normalized_session_id,),
                )
                deleted_promotions = int(cursor.rowcount or 0)
            conn.commit()

        if deleted_task_records:
            self._cleanup_abandoned_upload_files(deleted_task_records)

        return {
            "tasks": deleted_tasks,
            "attachment_promotions": deleted_promotions,
        }

    def prune(
        self,
        limit: int | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        effective_limit = max(0, self.history_limit if limit is None else int(limit))
        effective_ttl = max(0, self.ttl_seconds if ttl_seconds is None else int(ttl_seconds))
        now = time.time()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM tasks
                    WHERE status IN (%s, %s)
                      AND %s - updated_at > %s
                    """,
                    (
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                        now,
                        effective_ttl,
                    ),
                )
                cursor.execute(
                    """
                    DELETE FROM tasks
                    WHERE task_id IN (
                        SELECT task_id
                        FROM tasks
                        WHERE status IN (%s, %s)
                        ORDER BY updated_at DESC
                        OFFSET %s
                    )
                    """,
                    (
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                        effective_limit,
                    ),
                )
                cursor.execute(
                    """
                    DELETE FROM attachment_promotions
                    WHERE status IN (%s, %s)
                      AND NOT EXISTS (
                          SELECT 1
                          FROM tasks
                          WHERE tasks.task_id = attachment_promotions.task_id
                      )
                      AND %s - updated_at > %s
                    """,
                    (
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                        now,
                        effective_ttl,
                    ),
                )
                cursor.execute(
                    """
                    DELETE FROM attachment_promotions
                    WHERE ctid IN (
                        SELECT ctid
                        FROM attachment_promotions
                        WHERE status IN (%s, %s)
                          AND NOT EXISTS (
                              SELECT 1
                              FROM tasks
                              WHERE tasks.task_id = attachment_promotions.task_id
                          )
                        ORDER BY updated_at DESC, created_at DESC
                        OFFSET %s
                    )
                    """,
                    (
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                        effective_limit,
                    ),
                )
            conn.commit()
