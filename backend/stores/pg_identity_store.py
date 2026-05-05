"""PostgreSQL identity, organization, and membership store adapter."""

from __future__ import annotations

from typing import Any, Callable

from backend.stores.identity_store import (
    DEFAULT_ORG_ID,
    DEFAULT_ORG_NAME,
    MembershipRecord,
    OrganizationRecord,
    SQLiteIdentityStore,
    UserRecord,
    normalize_identity_role,
)
from backend.stores.pg_base import PostgresStoreMixin


class PostgresIdentityStore(PostgresStoreMixin, SQLiteIdentityStore):
    """PostgreSQL implementation for identity metadata."""

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
                    CREATE TABLE IF NOT EXISTS organizations (
                        org_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL,
                        email TEXT DEFAULT '',
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memberships (
                        org_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL,
                        PRIMARY KEY (org_id, user_id)
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id)"
                )
            conn.commit()

    def ensure_default_org(self, *, now: float) -> OrganizationRecord:
        existing = self.get_org(DEFAULT_ORG_ID)
        if existing is not None:
            return existing
        return self.upsert_org(
            org_id=DEFAULT_ORG_ID,
            name=DEFAULT_ORG_NAME,
            description="Default organization for local deployments.",
            now=now,
        )

    def upsert_org(
        self,
        *,
        org_id: str,
        name: str,
        description: str = "",
        now: float,
    ) -> OrganizationRecord:
        normalized_org_id = str(org_id or "").strip()
        normalized_name = str(name or "").strip()
        if not normalized_org_id:
            raise ValueError("org_id is required")
        if not normalized_name:
            raise ValueError("organization name is required")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO organizations (org_id, name, description, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(org_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        normalized_org_id,
                        normalized_name,
                        str(description or "").strip(),
                        now,
                        now,
                    ),
                )
            conn.commit()
        record = self.get_org(normalized_org_id)
        if record is None:
            raise RuntimeError("failed to upsert organization")
        return record

    def get_org(self, org_id: str) -> OrganizationRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT org_id, name, description, created_at, updated_at
                    FROM organizations
                    WHERE org_id = %s
                    """,
                    (str(org_id or "").strip(),),
                )
                row = cursor.fetchone()
        return self._org_from_row(row)

    def list_orgs(self, *, limit: int = 100) -> list[OrganizationRecord]:
        normalized_limit = max(1, min(int(limit or 100), 500))
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT org_id, name, description, created_at, updated_at
                    FROM organizations
                    ORDER BY updated_at DESC, org_id ASC
                    LIMIT %s
                    """,
                    (normalized_limit,),
                )
                rows = cursor.fetchall()
        return [record for row in rows if (record := self._org_from_row(row)) is not None]

    def upsert_user(
        self,
        *,
        user_id: str,
        display_name: str,
        email: str = "",
        now: float,
    ) -> UserRecord:
        normalized_user_id = str(user_id or "").strip()
        normalized_display_name = str(display_name or "").strip() or normalized_user_id
        if not normalized_user_id:
            raise ValueError("user_id is required")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (user_id, display_name, email, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(user_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        email = EXCLUDED.email,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        normalized_user_id,
                        normalized_display_name,
                        str(email or "").strip(),
                        now,
                        now,
                    ),
                )
            conn.commit()
        record = self.get_user(normalized_user_id)
        if record is None:
            raise RuntimeError("failed to upsert user")
        return record

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, display_name, email, created_at, updated_at
                    FROM users
                    WHERE user_id = %s
                    """,
                    (str(user_id or "").strip(),),
                )
                row = cursor.fetchone()
        return self._user_from_row(row)

    def list_users(self, *, limit: int = 100) -> list[UserRecord]:
        normalized_limit = max(1, min(int(limit or 100), 500))
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, display_name, email, created_at, updated_at
                    FROM users
                    ORDER BY updated_at DESC, user_id ASC
                    LIMIT %s
                    """,
                    (normalized_limit,),
                )
                rows = cursor.fetchall()
        return [record for row in rows if (record := self._user_from_row(row)) is not None]

    def set_membership(
        self,
        *,
        org_id: str,
        user_id: str,
        role: str,
        now: float,
    ) -> MembershipRecord:
        normalized_org_id = str(org_id or "").strip()
        normalized_user_id = str(user_id or "").strip()
        normalized_role = normalize_identity_role(role)
        if not normalized_org_id or not normalized_user_id:
            raise ValueError("org_id and user_id are required")
        if self.get_org(normalized_org_id) is None:
            raise ValueError("organization not found")
        if self.get_user(normalized_user_id) is None:
            raise ValueError("user not found")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO memberships (org_id, user_id, role, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(org_id, user_id) DO UPDATE SET
                        role = EXCLUDED.role,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (normalized_org_id, normalized_user_id, normalized_role, now, now),
                )
            conn.commit()
        record = self.get_membership(org_id=normalized_org_id, user_id=normalized_user_id)
        if record is None:
            raise RuntimeError("failed to set membership")
        return record

    def get_membership(self, *, org_id: str, user_id: str) -> MembershipRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT org_id, user_id, role, created_at, updated_at
                    FROM memberships
                    WHERE org_id = %s AND user_id = %s
                    """,
                    (str(org_id or "").strip(), str(user_id or "").strip()),
                )
                row = cursor.fetchone()
        return self._membership_from_row(row)

    def list_memberships(
        self,
        *,
        org_id: str = "",
        user_id: str = "",
        limit: int = 100,
    ) -> list[MembershipRecord]:
        normalized_limit = max(1, min(int(limit or 100), 500))
        clauses: list[str] = []
        values: list[Any] = []
        if str(org_id or "").strip():
            clauses.append("org_id = %s")
            values.append(str(org_id or "").strip())
        if str(user_id or "").strip():
            clauses.append("user_id = %s")
            values.append(str(user_id or "").strip())
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT org_id, user_id, role, created_at, updated_at
                    FROM memberships
                    {where_sql}
                    ORDER BY updated_at DESC, org_id ASC, user_id ASC
                    LIMIT %s
                    """,
                    (*values, normalized_limit),
                )
                rows = cursor.fetchall()
        return [
            record
            for row in rows
            if (record := self._membership_from_row(row)) is not None
        ]
