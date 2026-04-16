import json
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from chat_store import connect_sqlite


def _now_timestamp() -> float:
    return time.time()


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_optional_text(value: Any) -> str | None:
    normalized = _normalize_text(value)
    return normalized or None


class ArtifactRecord(BaseModel):
    artifact_id: str
    session_id: str
    artifact_type: str
    title: str
    status: str = "ready"
    linked_resource_type: str | None = None
    linked_resource_id: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=_now_timestamp)
    updated_at: float = Field(default_factory=_now_timestamp)


def artifact_export_formats(artifact: ArtifactRecord) -> list[str]:
    if artifact.artifact_type == "report":
        return ["md", "pptx"]
    if artifact.artifact_type == "deck":
        return ["pptx"]
    return []


def build_report_artifact(
    *,
    session_id: str,
    title: str,
    markdown: str,
    qa_pairs: list[tuple[str, str]],
    answer_group_id: str = "",
    panel_id: str = "",
    artifact_id: str | None = None,
) -> ArtifactRecord:
    now = _now_timestamp()
    return ArtifactRecord(
        artifact_id=artifact_id or f"artifact_{uuid.uuid4().hex}",
        session_id=_normalize_text(session_id),
        artifact_type="report",
        title=_normalize_text(title) or "AI 对话报告",
        status="ready",
        content={
            "markdown": str(markdown or ""),
            "qa_pairs": [
                {
                    "question": _normalize_text(question),
                    "answer": str(answer or "").strip(),
                }
                for question, answer in qa_pairs
                if _normalize_text(question) or str(answer or "").strip()
            ],
            "answer_group_id": _normalize_optional_text(answer_group_id),
            "panel_id": _normalize_optional_text(panel_id),
        },
        created_at=now,
        updated_at=now,
    )


def build_deck_artifact(
    deck: Any,
    *,
    artifact_id: str | None = None,
) -> ArtifactRecord:
    now = _now_timestamp()
    return ArtifactRecord(
        artifact_id=artifact_id or f"artifact_{uuid.uuid4().hex}",
        session_id=_normalize_text(getattr(getattr(deck, "meta", None), "session_id", "")),
        artifact_type="deck",
        title=_normalize_text(getattr(getattr(deck, "meta", None), "title", "")) or "Deck Draft",
        status=_normalize_text(getattr(deck, "status", "")) or "draft",
        linked_resource_type="deck",
        linked_resource_id=_normalize_optional_text(getattr(deck, "deck_id", "")),
        content={
            "deck_id": _normalize_text(getattr(deck, "deck_id", "")),
            "theme": _normalize_text(getattr(getattr(deck, "meta", None), "theme", "")) or "default",
            "slide_count": int(
                getattr(getattr(deck, "generation", None), "actual_slide_count", 0) or 0
            ),
            "answer_group_id": _normalize_optional_text(
                getattr(getattr(deck, "meta", None), "source_answer_group_id", "")
            ),
            "panel_id": _normalize_optional_text(
                getattr(getattr(deck, "meta", None), "source_panel_id", "")
            ),
        },
        created_at=now,
        updated_at=now,
    )


def sync_deck_artifact(artifact: ArtifactRecord, deck: Any) -> ArtifactRecord:
    artifact.session_id = _normalize_text(getattr(getattr(deck, "meta", None), "session_id", ""))
    artifact.title = _normalize_text(getattr(getattr(deck, "meta", None), "title", "")) or artifact.title
    artifact.status = _normalize_text(getattr(deck, "status", "")) or artifact.status
    artifact.linked_resource_type = "deck"
    artifact.linked_resource_id = _normalize_optional_text(getattr(deck, "deck_id", ""))
    artifact.content = {
        "deck_id": _normalize_text(getattr(deck, "deck_id", "")),
        "theme": _normalize_text(getattr(getattr(deck, "meta", None), "theme", "")) or "default",
        "slide_count": int(
            getattr(getattr(deck, "generation", None), "actual_slide_count", 0) or 0
        ),
        "answer_group_id": _normalize_optional_text(
            getattr(getattr(deck, "meta", None), "source_answer_group_id", "")
        ),
        "panel_id": _normalize_optional_text(
            getattr(getattr(deck, "meta", None), "source_panel_id", "")
        ),
    }
    artifact.updated_at = _now_timestamp()
    return artifact


class SQLiteArtifactStore:
    def __init__(self, db_path: str = "./chat_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
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
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_session
                ON artifacts(session_id, updated_at DESC, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_linked_resource
                ON artifacts(linked_resource_type, linked_resource_id, updated_at DESC)
                """
            )
            conn.commit()

    def save(self, artifact: ArtifactRecord) -> ArtifactRecord:
        self._init_db()
        now = _now_timestamp()
        created_at = float(getattr(artifact, "created_at", now) or now)
        artifact.updated_at = now
        payload = json.dumps(artifact.content, ensure_ascii=False)
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id,
                    session_id,
                    artifact_type,
                    title,
                    status,
                    linked_resource_type,
                    linked_resource_id,
                    content_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    artifact_type = excluded.artifact_type,
                    title = excluded.title,
                    status = excluded.status,
                    linked_resource_type = excluded.linked_resource_type,
                    linked_resource_id = excluded.linked_resource_id,
                    content_json = excluded.content_json,
                    updated_at = excluded.updated_at
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

    def get(self, artifact_id: str) -> ArtifactRecord:
        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    artifact_id,
                    session_id,
                    artifact_type,
                    title,
                    status,
                    linked_resource_type,
                    linked_resource_id,
                    content_json,
                    created_at,
                    updated_at
                FROM artifacts
                WHERE artifact_id = ?
                """,
                (str(artifact_id or "").strip(),),
            ).fetchone()
        if not row:
            raise KeyError(str(artifact_id or "").strip())
        return ArtifactRecord(
            artifact_id=str(row[0] or ""),
            session_id=str(row[1] or ""),
            artifact_type=str(row[2] or ""),
            title=str(row[3] or ""),
            status=str(row[4] or "") or "ready",
            linked_resource_type=_normalize_optional_text(row[5]),
            linked_resource_id=_normalize_optional_text(row[6]),
            content=json.loads(row[7] or "{}"),
            created_at=float(row[8] or 0),
            updated_at=float(row[9] or 0),
        )

    def list_by_session(
        self,
        session_id: str,
        *,
        artifact_type: str = "",
    ) -> list[ArtifactRecord]:
        normalized_session_id = _normalize_text(session_id)
        if not normalized_session_id:
            return []

        self._init_db()
        query = """
            SELECT artifact_id
            FROM artifacts
            WHERE session_id = ?
        """
        params: list[Any] = [normalized_session_id]
        normalized_artifact_type = _normalize_text(artifact_type)
        if normalized_artifact_type:
            query += " AND artifact_type = ?"
            params.append(normalized_artifact_type)
        query += " ORDER BY updated_at DESC, created_at DESC"
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self.get(str(row[0] or "")) for row in rows if row and row[0]]

    def list_by_linked_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> list[ArtifactRecord]:
        normalized_resource_type = _normalize_text(resource_type)
        normalized_resource_id = _normalize_text(resource_id)
        if not normalized_resource_type or not normalized_resource_id:
            return []

        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT artifact_id
                FROM artifacts
                WHERE linked_resource_type = ? AND linked_resource_id = ?
                ORDER BY updated_at DESC, created_at DESC
                """,
                (normalized_resource_type, normalized_resource_id),
            ).fetchall()
        return [self.get(str(row[0] or "")) for row in rows if row and row[0]]

    def delete_by_session(self, session_id: str) -> int:
        normalized_session_id = _normalize_text(session_id)
        if not normalized_session_id:
            return 0

        self._init_db()
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM artifacts WHERE session_id = ?",
                (normalized_session_id,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
