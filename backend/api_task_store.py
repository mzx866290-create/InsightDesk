import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from backend.chat_store import connect_sqlite

logger = logging.getLogger(__name__)

RESTART_FAILURE_MESSAGE = "服务已重启，任务未能继续执行，请重新发起。"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    status: TaskStatus
    params: dict
    session_id: Optional[str]
    created_at: float
    updated_at: float
    result: Optional[str] = None
    error: Optional[str] = None
    progress: int = 0


@dataclass
class AttachmentPromotionRecord:
    attachment_id: str
    vector_store_path: str
    task_id: str
    status: TaskStatus
    attachment_name: str
    session_id: Optional[str]
    created_at: float
    updated_at: float
    result: Optional[str] = None
    error: Optional[str] = None


class SQLiteTaskStore:
    def __init__(
        self,
        db_path: str = "./chat_history.db",
        *,
        history_limit: int = 200,
        ttl_seconds: int = 6 * 60 * 60,
    ):
        self.db_path = db_path
        self.history_limit = int(history_limit)
        self.ttl_seconds = int(ttl_seconds)
        self._init_db()
        self._fail_incomplete_tasks()
        self.prune()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    session_id TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    result TEXT,
                    error TEXT,
                    progress INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_created
                ON tasks(created_at DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_updated
                ON tasks(updated_at DESC, created_at DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_status_updated
                ON tasks(status, updated_at DESC)
                """
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
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    result TEXT,
                    error TEXT,
                    PRIMARY KEY (attachment_id, vector_store_path)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_attachment_promotions_task
                ON attachment_promotions(task_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_attachment_promotions_status_updated
                ON attachment_promotions(status, updated_at DESC, created_at DESC)
                """
            )
            conn.commit()

    @staticmethod
    def _from_row(row: tuple[Any, ...] | None) -> TaskRecord | None:
        if row is None:
            return None
        (
            task_id,
            task_type,
            status,
            params_json,
            session_id,
            created_at,
            updated_at,
            result,
            error,
            progress,
        ) = row
        try:
            params = json.loads(params_json or "{}")
        except json.JSONDecodeError:
            params = {}
        return TaskRecord(
            task_id=str(task_id),
            task_type=str(task_type),
            status=TaskStatus(str(status)),
            params=params if isinstance(params, dict) else {},
            session_id=str(session_id) if session_id else None,
            created_at=float(created_at),
            updated_at=float(updated_at),
            result=str(result) if result is not None else None,
            error=str(error) if error is not None else None,
            progress=int(progress or 0),
        )

    @staticmethod
    def _promotion_from_row(
        row: tuple[Any, ...] | None,
    ) -> AttachmentPromotionRecord | None:
        if row is None:
            return None
        (
            attachment_id,
            vector_store_path,
            task_id,
            status,
            attachment_name,
            session_id,
            created_at,
            updated_at,
            result,
            error,
        ) = row
        return AttachmentPromotionRecord(
            attachment_id=str(attachment_id),
            vector_store_path=str(vector_store_path),
            task_id=str(task_id),
            status=TaskStatus(str(status)),
            attachment_name=str(attachment_name or ""),
            session_id=str(session_id) if session_id else None,
            created_at=float(created_at),
            updated_at=float(updated_at),
            result=str(result) if result is not None else None,
            error=str(error) if error is not None else None,
        )

    def save(self, record: TaskRecord) -> TaskRecord:
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, task_type, status, params_json, session_id,
                    created_at, updated_at, result, error, progress
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    task_type = excluded.task_type,
                    status = excluded.status,
                    params_json = excluded.params_json,
                    session_id = excluded.session_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    result = excluded.result,
                    error = excluded.error,
                    progress = excluded.progress
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
            self._save_attachment_promotion_for_task(conn, record)
            conn.commit()
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    task_id, task_type, status, params_json, session_id,
                    created_at, updated_at, result, error, progress
                FROM tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._from_row(row)

    def list_recent(self, limit: int = 20) -> list[TaskRecord]:
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    task_id, task_type, status, params_json, session_id,
                    created_at, updated_at, result, error, progress
                FROM tasks
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [record for row in rows if (record := self._from_row(row)) is not None]

    def _save_attachment_promotion_for_task(self, conn: Any, record: TaskRecord) -> None:
        if record.task_type != "promote_attachment_to_kb":
            return

        attachment_id = str(record.params.get("attachment_id") or "").strip()
        vector_store_path = str(record.params.get("vector_store_path") or "").strip()
        attachment_name = str(record.params.get("attachment_name") or "").strip()
        if not attachment_id or not vector_store_path:
            return

        existing_row = conn.execute(
            """
            SELECT created_at
            FROM attachment_promotions
            WHERE attachment_id = ? AND vector_store_path = ?
            """,
            (attachment_id, vector_store_path),
        ).fetchone()
        created_at = (
            float(existing_row[0])
            if existing_row and existing_row[0] is not None
            else record.created_at
        )

        conn.execute(
            """
            INSERT INTO attachment_promotions (
                attachment_id, vector_store_path, task_id, status,
                attachment_name, session_id, created_at, updated_at, result, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(attachment_id, vector_store_path) DO UPDATE SET
                task_id = excluded.task_id,
                status = excluded.status,
                attachment_name = excluded.attachment_name,
                session_id = excluded.session_id,
                updated_at = excluded.updated_at,
                result = excluded.result,
                error = excluded.error
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

    def get_attachment_promotion(
        self,
        attachment_id: str,
        vector_store_path: str,
    ) -> AttachmentPromotionRecord | None:
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    attachment_id, vector_store_path, task_id, status,
                    attachment_name, session_id, created_at, updated_at, result, error
                FROM attachment_promotions
                WHERE attachment_id = ? AND vector_store_path = ?
                """,
                (attachment_id, vector_store_path),
            ).fetchone()
        return self._promotion_from_row(row)

    def get_attachment_promotion_task(
        self,
        attachment_id: str,
        vector_store_path: str,
    ) -> TaskRecord | None:
        promotion = self.get_attachment_promotion(attachment_id, vector_store_path)
        if promotion is None:
            return None

        task = self.get(promotion.task_id)
        if task is not None:
            return task

        progress = 100 if promotion.status == TaskStatus.COMPLETED else 0
        return TaskRecord(
            task_id=promotion.task_id,
            task_type="promote_attachment_to_kb",
            status=promotion.status,
            params={
                "attachment_id": promotion.attachment_id,
                "attachment_name": promotion.attachment_name,
                "vector_store_path": promotion.vector_store_path,
            },
            session_id=promotion.session_id,
            created_at=promotion.created_at,
            updated_at=promotion.updated_at,
            result=promotion.result,
            error=promotion.error,
            progress=progress,
        )

    def delete_for_session(self, session_id: str) -> dict[str, int]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return {"tasks": 0, "attachment_promotions": 0}

        self._init_db()
        deleted_task_records: list[TaskRecord] = []
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                """
                SELECT
                    task_id, task_type, status, params_json, session_id,
                    created_at, updated_at, result, error, progress
                FROM tasks
                WHERE session_id = ?
                """,
                (normalized_session_id,),
            ).fetchall()
            deleted_task_records = [
                record for row in rows if (record := self._from_row(row)) is not None
            ]
            cursor.execute(
                "DELETE FROM tasks WHERE session_id = ?",
                (normalized_session_id,),
            )
            deleted_tasks = int(cursor.rowcount or 0)
            cursor.execute(
                "DELETE FROM attachment_promotions WHERE session_id = ?",
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

    def _cleanup_abandoned_upload_files(self, records: list[TaskRecord]) -> None:
        for record in records:
            if record.task_type != "upload_documents":
                continue
            for temp_path in record.params.get("temp_paths", []):
                if not temp_path:
                    continue
                try:
                    os.remove(str(temp_path))
                except OSError:
                    pass

    def _fail_incomplete_tasks(self) -> None:
        stale_records: list[TaskRecord] = []
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    task_id, task_type, status, params_json, session_id,
                    created_at, updated_at, result, error, progress
                FROM tasks
                WHERE status IN (?, ?)
                """,
                (TaskStatus.PENDING.value, TaskStatus.RUNNING.value),
            ).fetchall()
            stale_records = [
                record for row in rows if (record := self._from_row(row)) is not None
            ]
            if stale_records:
                now = time.time()
                conn.executemany(
                    """
                    UPDATE tasks
                    SET status = ?, updated_at = ?, error = ?, progress = CASE WHEN progress >= 100 THEN progress ELSE 0 END
                    WHERE task_id = ?
                    """,
                    [
                        (
                            TaskStatus.FAILED.value,
                            now,
                            RESTART_FAILURE_MESSAGE,
                            record.task_id,
                        )
                        for record in stale_records
                    ],
                )
                conn.commit()
        if stale_records:
            now = time.time()
            for record in stale_records:
                record.status = TaskStatus.FAILED
                record.updated_at = now
                record.error = RESTART_FAILURE_MESSAGE
                if record.progress < 100:
                    record.progress = 0
                self.save(record)
            self._cleanup_abandoned_upload_files(stale_records)
            logger.info(
                "Marked %d incomplete task(s) as failed after restart",
                len(stale_records),
            )

    def prune(
        self,
        limit: int | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        effective_limit = max(0, self.history_limit if limit is None else int(limit))
        effective_ttl = max(0, self.ttl_seconds if ttl_seconds is None else int(ttl_seconds))
        with connect_sqlite(self.db_path) as conn:
            now = time.time()
            conn.execute(
                """
                DELETE FROM tasks
                WHERE status IN (?, ?)
                  AND ? - updated_at > ?
                """,
                (
                    TaskStatus.COMPLETED.value,
                    TaskStatus.FAILED.value,
                    now,
                    effective_ttl,
                ),
            )

            terminal_rows = conn.execute(
                """
                SELECT task_id
                FROM tasks
                WHERE status IN (?, ?)
                ORDER BY updated_at DESC
                """,
                (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value),
            ).fetchall()
            stale_ids = (
                [row[0] for row in terminal_rows[effective_limit:]]
                if len(terminal_rows) > effective_limit
                else []
            )
            if stale_ids:
                conn.executemany(
                    "DELETE FROM tasks WHERE task_id = ?",
                    [(task_id,) for task_id in stale_ids],
                )
            self._prune_orphaned_attachment_promotions(
                conn,
                limit=effective_limit,
                ttl_seconds=effective_ttl,
                now=now,
            )
            conn.commit()

    def _prune_orphaned_attachment_promotions(
        self,
        conn: Any,
        *,
        limit: int,
        ttl_seconds: int,
        now: float,
    ) -> None:
        conn.execute(
            """
            DELETE FROM attachment_promotions
            WHERE status IN (?, ?)
              AND NOT EXISTS (
                  SELECT 1
                  FROM tasks
                  WHERE tasks.task_id = attachment_promotions.task_id
              )
              AND ? - updated_at > ?
            """,
            (
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                now,
                ttl_seconds,
            ),
        )

        orphan_rows = conn.execute(
            """
            SELECT attachment_id, vector_store_path
            FROM attachment_promotions
            WHERE status IN (?, ?)
              AND NOT EXISTS (
                  SELECT 1
                  FROM tasks
                  WHERE tasks.task_id = attachment_promotions.task_id
              )
            ORDER BY updated_at DESC, created_at DESC
            """,
            (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value),
        ).fetchall()
        stale_rows = orphan_rows[limit:] if len(orphan_rows) > limit else []
        if stale_rows:
            conn.executemany(
                """
                DELETE FROM attachment_promotions
                WHERE attachment_id = ? AND vector_store_path = ?
                """,
                [(attachment_id, vector_store_path) for attachment_id, vector_store_path in stale_rows],
            )
