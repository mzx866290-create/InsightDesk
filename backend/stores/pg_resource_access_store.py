"""PostgreSQL resource access grant store adapter."""

from __future__ import annotations

from typing import Any, Callable

from backend.stores.identity_store import IDENTITY_ROLE_RANKS, normalize_identity_role
from backend.stores.pg_base import PostgresStoreMixin
from backend.stores.resource_access_store import (
    RESOURCE_SUBJECT_TYPES,
    ResourceAccessRecord,
    ResourceGrantRecord,
    SQLiteResourceAccessStore,
    _normalize_resource_key,
    _subject_key,
)


class PostgresResourceAccessStore(PostgresStoreMixin, SQLiteResourceAccessStore):
    """PostgreSQL implementation for explicit resource ACL grants."""

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
                    CREATE TABLE IF NOT EXISTS resource_grants (
                        resource_type TEXT NOT NULL,
                        resource_id TEXT NOT NULL,
                        subject_type TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL,
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

    def _record_from_row(self, row: Any | None) -> ResourceGrantRecord | None:
        if row is None:
            return None
        subject_type = str(self._row_value(row, 2, "subject_type") or "").strip()
        subject_id = str(self._row_value(row, 3, "subject_id") or "").strip()
        return ResourceGrantRecord(
            resource_type=str(self._row_value(row, 0, "resource_type") or ""),
            resource_id=str(self._row_value(row, 1, "resource_id") or ""),
            org_id=subject_id if subject_type == "org" else "",
            user_id=subject_id if subject_type == "user" else "",
            role=normalize_identity_role(self._row_value(row, 4, "role")),
            created_at=float(self._row_value(row, 5, "created_at") or 0),
            updated_at=float(self._row_value(row, 6, "updated_at") or 0),
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
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO resource_grants (
                        resource_type, resource_id, subject_type, subject_id,
                        role, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(resource_type, resource_id, subject_type, subject_id)
                    DO UPDATE SET
                        role = EXCLUDED.role,
                        updated_at = EXCLUDED.updated_at
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
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT resource_type, resource_id, subject_type, subject_id,
                           role, created_at, updated_at
                    FROM resource_grants
                    WHERE resource_type = %s
                      AND resource_id = %s
                      AND subject_type = %s
                      AND subject_id = %s
                    """,
                    (
                        str(resource_type or "").strip(),
                        str(resource_id or "").strip(),
                        subject_type,
                        subject_id,
                    ),
                )
                row = cursor.fetchone()
        return self._record_from_row(row)

    def _filter_clauses(
        self,
        *,
        resource_type: str = "",
        resource_id: str = "",
        org_id: str = "",
        user_id: str = "",
        role: str = "",
        subject_type: str = "",
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("resource_type", resource_type),
            ("resource_id", resource_id),
        ):
            normalized_value = str(value or "").strip()
            if normalized_value:
                clauses.append(f"{column} = %s")
                values.append(normalized_value)
        normalized_role = (
            normalize_identity_role(role, default="")
            if str(role or "").strip()
            else ""
        )
        normalized_subject_type = str(subject_type or "").strip().lower()
        if normalized_subject_type and normalized_subject_type not in RESOURCE_SUBJECT_TYPES:
            raise ValueError("subject_type must be user or org")
        if str(org_id or "").strip() and str(user_id or "").strip():
            raise ValueError("org_id and user_id filters cannot be combined")
        if str(org_id or "").strip():
            clauses.extend(["subject_type = %s", "subject_id = %s"])
            values.extend(["org", str(org_id or "").strip()])
        elif str(user_id or "").strip():
            clauses.extend(["subject_type = %s", "subject_id = %s"])
            values.extend(["user", str(user_id or "").strip()])
        elif normalized_subject_type:
            clauses.append("subject_type = %s")
            values.append(normalized_subject_type)
        if normalized_role:
            clauses.append("role = %s")
            values.append(normalized_role)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, values

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
        where_sql, values = self._filter_clauses(
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            user_id=user_id,
            role=role,
            subject_type=subject_type,
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT resource_type, resource_id, subject_type, subject_id,
                           role, created_at, updated_at
                    FROM resource_grants
                    {where_sql}
                    ORDER BY updated_at DESC, resource_type ASC, resource_id ASC
                    LIMIT %s OFFSET %s
                    """,
                    (*values, normalized_limit, normalized_offset),
                )
                rows = cursor.fetchall()
        return [record for row in rows if (record := self._record_from_row(row)) is not None]

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
        where_sql, values = self._filter_clauses(
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            user_id=user_id,
            role=role,
            subject_type=subject_type,
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) FROM resource_grants {where_sql}",
                    tuple(values),
                )
                row = cursor.fetchone()
        return int(self._row_value(row, 0, "count") if row else 0)

    def delete_grant(
        self,
        *,
        resource_type: str,
        resource_id: str,
        org_id: str = "",
        user_id: str = "",
    ) -> bool:
        subject_type, subject_id = _subject_key(org_id=org_id, user_id=user_id)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM resource_grants
                    WHERE resource_type = %s
                      AND resource_id = %s
                      AND subject_type = %s
                      AND subject_id = %s
                    """,
                    (
                        str(resource_type or "").strip(),
                        str(resource_id or "").strip(),
                        subject_type,
                        subject_id,
                    ),
                )
                deleted = int(cursor.rowcount or 0) > 0
            conn.commit()
        return deleted

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
                    role for role, rank in IDENTITY_ROLE_RANKS.items() if rank == effective_rank
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
