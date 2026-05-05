"""Resource-level access grant persistence.

This store is intentionally small: it records explicit user/org grants for a
resource. Enforcement can be attached route-by-route without changing the
persistence contract again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.chat_store import connect_sqlite
from backend.core.storage_runtime import app_database_path
from backend.stores.identity_store import IDENTITY_ROLE_RANKS, normalize_identity_role


RESOURCE_SUBJECT_TYPES = {"user", "org"}


@dataclass
class ResourceGrantRecord:
    resource_type: str
    resource_id: str
    org_id: str = ""
    user_id: str = ""
    role: str = "viewer"
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class ResourceAccessRecord:
    resource_type: str
    resource_id: str
    user_id: str
    role: str = ""
    allowed: bool = False
    source: str = "none"


def _normalize_resource_key(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _subject_key(*, org_id: str = "", user_id: str = "") -> tuple[str, str]:
    normalized_org_id = str(org_id or "").strip()
    normalized_user_id = str(user_id or "").strip()
    if bool(normalized_org_id) == bool(normalized_user_id):
        raise ValueError("exactly one of org_id or user_id is required")
    if normalized_org_id:
        return "org", normalized_org_id
    return "user", normalized_user_id


class SQLiteResourceAccessStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or app_database_path()).strip()
        self._init_db()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS resource_grants (
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (resource_type, resource_id, subject_type, subject_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_resource_grants_subject
                ON resource_grants(subject_type, subject_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_resource_grants_resource
                ON resource_grants(resource_type, resource_id)
                """
            )
            conn.commit()

    @staticmethod
    def _record_from_row(row: tuple[Any, ...] | None) -> ResourceGrantRecord | None:
        if row is None:
            return None
        subject_type = str(row[2] or "").strip()
        subject_id = str(row[3] or "").strip()
        return ResourceGrantRecord(
            resource_type=str(row[0] or ""),
            resource_id=str(row[1] or ""),
            org_id=subject_id if subject_type == "org" else "",
            user_id=subject_id if subject_type == "user" else "",
            role=normalize_identity_role(row[4]),
            created_at=float(row[5] or 0),
            updated_at=float(row[6] or 0),
        )

    def upsert_grant(
        self,
        *,
        resource_type: str,
        resource_id: str,
        role: str,
        now: float,
        org_id: str = "",
        user_id: str = "",
    ) -> ResourceGrantRecord:
        normalized_resource_type = _normalize_resource_key(
            resource_type, field_name="resource_type"
        )
        normalized_resource_id = _normalize_resource_key(
            resource_id, field_name="resource_id"
        )
        subject_type, subject_id = _subject_key(org_id=org_id, user_id=user_id)
        normalized_role = normalize_identity_role(role)
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO resource_grants (
                    resource_type, resource_id, subject_type, subject_id,
                    role, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(resource_type, resource_id, subject_type, subject_id)
                DO UPDATE SET
                    role=excluded.role,
                    updated_at=excluded.updated_at
                """,
                (
                    normalized_resource_type,
                    normalized_resource_id,
                    subject_type,
                    subject_id,
                    normalized_role,
                    now,
                    now,
                ),
            )
            conn.commit()
        record = self.get_grant(
            resource_type=normalized_resource_type,
            resource_id=normalized_resource_id,
            org_id=subject_id if subject_type == "org" else "",
            user_id=subject_id if subject_type == "user" else "",
        )
        if record is None:
            raise RuntimeError("failed to upsert resource grant")
        return record

    def get_grant(
        self,
        *,
        resource_type: str,
        resource_id: str,
        org_id: str = "",
        user_id: str = "",
    ) -> ResourceGrantRecord | None:
        subject_type, subject_id = _subject_key(org_id=org_id, user_id=user_id)
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT resource_type, resource_id, subject_type, subject_id,
                       role, created_at, updated_at
                FROM resource_grants
                WHERE resource_type = ?
                  AND resource_id = ?
                  AND subject_type = ?
                  AND subject_id = ?
                """,
                (
                    str(resource_type or "").strip(),
                    str(resource_id or "").strip(),
                    subject_type,
                    subject_id,
                ),
            ).fetchone()
        return self._record_from_row(row)

    def list_grants(
        self,
        *,
        resource_type: str = "",
        resource_id: str = "",
        org_id: str = "",
        user_id: str = "",
        limit: int = 100,
        offset: int = 0,
        role: str = "",
        subject_type: str = "",
    ) -> list[ResourceGrantRecord]:
        normalized_limit = max(1, min(int(limit or 100), 500))
        normalized_offset = max(0, int(offset or 0))
        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("resource_type", resource_type),
            ("resource_id", resource_id),
        ):
            normalized_value = str(value or "").strip()
            if normalized_value:
                clauses.append(f"{column} = ?")
                values.append(normalized_value)
        normalized_role = normalize_identity_role(role, default="") if str(role or "").strip() else ""
        normalized_subject_type = str(subject_type or "").strip().lower()
        if normalized_subject_type and normalized_subject_type not in RESOURCE_SUBJECT_TYPES:
            raise ValueError("subject_type must be user or org")
        if str(org_id or "").strip() and str(user_id or "").strip():
            raise ValueError("org_id and user_id filters cannot be combined")
        if str(org_id or "").strip():
            clauses.extend(["subject_type = ?", "subject_id = ?"])
            values.extend(["org", str(org_id or "").strip()])
        elif str(user_id or "").strip():
            clauses.extend(["subject_type = ?", "subject_id = ?"])
            values.extend(["user", str(user_id or "").strip()])
        elif normalized_subject_type:
            clauses.append("subject_type = ?")
            values.append(normalized_subject_type)
        if normalized_role:
            clauses.append("role = ?")
            values.append(normalized_role)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT resource_type, resource_id, subject_type, subject_id,
                       role, created_at, updated_at
                FROM resource_grants
                {where_sql}
                ORDER BY updated_at DESC, resource_type ASC, resource_id ASC
                LIMIT ? OFFSET ?
                """,
                (*values, normalized_limit, normalized_offset),
            ).fetchall()
        return [
            record for row in rows if (record := self._record_from_row(row)) is not None
        ]

    def count_grants(
        self,
        *,
        resource_type: str = "",
        resource_id: str = "",
        org_id: str = "",
        user_id: str = "",
        role: str = "",
        subject_type: str = "",
    ) -> int:
        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("resource_type", resource_type),
            ("resource_id", resource_id),
        ):
            normalized_value = str(value or "").strip()
            if normalized_value:
                clauses.append(f"{column} = ?")
                values.append(normalized_value)
        normalized_role = normalize_identity_role(role, default="") if str(role or "").strip() else ""
        normalized_subject_type = str(subject_type or "").strip().lower()
        if normalized_subject_type and normalized_subject_type not in RESOURCE_SUBJECT_TYPES:
            raise ValueError("subject_type must be user or org")
        if str(org_id or "").strip() and str(user_id or "").strip():
            raise ValueError("org_id and user_id filters cannot be combined")
        if str(org_id or "").strip():
            clauses.extend(["subject_type = ?", "subject_id = ?"])
            values.extend(["org", str(org_id or "").strip()])
        elif str(user_id or "").strip():
            clauses.extend(["subject_type = ?", "subject_id = ?"])
            values.extend(["user", str(user_id or "").strip()])
        elif normalized_subject_type:
            clauses.append("subject_type = ?")
            values.append(normalized_subject_type)
        if normalized_role:
            clauses.append("role = ?")
            values.append(normalized_role)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM resource_grants {where_sql}",
                tuple(values),
            ).fetchone()
        return int(row[0] if row else 0)


    def delete_grant(
        self,
        *,
        resource_type: str,
        resource_id: str,
        org_id: str = "",
        user_id: str = "",
    ) -> bool:
        subject_type, subject_id = _subject_key(org_id=org_id, user_id=user_id)
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM resource_grants
                WHERE resource_type = ?
                  AND resource_id = ?
                  AND subject_type = ?
                  AND subject_id = ?
                """,
                (
                    str(resource_type or "").strip(),
                    str(resource_id or "").strip(),
                    subject_type,
                    subject_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def resolve_user_access(
        self,
        *,
        resource_type: str,
        resource_id: str,
        user_id: str,
        identity_store: Any,
        minimum_role: str = "viewer",
    ) -> ResourceAccessRecord:
        normalized_resource_type = str(resource_type or "").strip()
        normalized_resource_id = str(resource_id or "").strip()
        normalized_user_id = str(user_id or "").strip()
        minimum_rank = IDENTITY_ROLE_RANKS[normalize_identity_role(minimum_role)]
        best_role = ""
        best_rank = 0
        source = "none"

        for grant in self.list_grants(
            resource_type=normalized_resource_type,
            resource_id=normalized_resource_id,
            user_id=normalized_user_id,
            limit=100,
        ):
            grant_rank = IDENTITY_ROLE_RANKS[normalize_identity_role(grant.role)]
            if grant_rank > best_rank:
                best_role = grant.role
                best_rank = grant_rank
                source = "user_grant"

        memberships = identity_store.list_memberships(user_id=normalized_user_id, limit=500)
        for membership in memberships:
            org_grant = self.get_grant(
                resource_type=normalized_resource_type,
                resource_id=normalized_resource_id,
                org_id=membership.org_id,
            )
            if org_grant is None:
                continue
            grant_rank = IDENTITY_ROLE_RANKS[normalize_identity_role(org_grant.role)]
            membership_rank = IDENTITY_ROLE_RANKS[normalize_identity_role(membership.role)]
            effective_rank = min(grant_rank, membership_rank)
            if effective_rank > best_rank:
                best_role = next(
                    role
                    for role, rank in IDENTITY_ROLE_RANKS.items()
                    if rank == effective_rank
                )
                best_rank = effective_rank
                source = "org_grant"

        return ResourceAccessRecord(
            resource_type=normalized_resource_type,
            resource_id=normalized_resource_id,
            user_id=normalized_user_id,
            role=best_role,
            allowed=best_rank >= minimum_rank,
            source=source,
        )
