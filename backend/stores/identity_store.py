"""Identity, organization, and membership persistence store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.chat_store import connect_sqlite
from backend.core.storage_runtime import app_database_path

DEFAULT_ORG_ID = "org-default"
DEFAULT_ORG_NAME = "????"
IDENTITY_ROLE_RANKS = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


@dataclass
class OrganizationRecord:
    org_id: str
    name: str
    description: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class UserRecord:
    user_id: str
    display_name: str
    email: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class MembershipRecord:
    org_id: str
    user_id: str
    role: str
    created_at: float = 0.0
    updated_at: float = 0.0


def normalize_identity_role(role: Any, *, default: str = "viewer") -> str:
    normalized = str(role or "").strip().lower()
    return normalized if normalized in IDENTITY_ROLE_RANKS else default


class SQLiteIdentityStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or app_database_path()).strip()
        self._init_db()

    def _init_db(self) -> None:
        with connect_sqlite(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    email TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memberships (
                    org_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (org_id, user_id),
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id)"
            )
            conn.commit()

    @staticmethod
    def _org_from_row(row: tuple[Any, ...] | None) -> OrganizationRecord | None:
        if row is None:
            return None
        return OrganizationRecord(
            org_id=str(row[0] or ""),
            name=str(row[1] or ""),
            description=str(row[2] or ""),
            created_at=float(row[3] or 0),
            updated_at=float(row[4] or 0),
        )

    @staticmethod
    def _user_from_row(row: tuple[Any, ...] | None) -> UserRecord | None:
        if row is None:
            return None
        return UserRecord(
            user_id=str(row[0] or ""),
            display_name=str(row[1] or ""),
            email=str(row[2] or ""),
            created_at=float(row[3] or 0),
            updated_at=float(row[4] or 0),
        )

    @staticmethod
    def _membership_from_row(row: tuple[Any, ...] | None) -> MembershipRecord | None:
        if row is None:
            return None
        return MembershipRecord(
            org_id=str(row[0] or ""),
            user_id=str(row[1] or ""),
            role=normalize_identity_role(row[2]),
            created_at=float(row[3] or 0),
            updated_at=float(row[4] or 0),
        )

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
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO organizations (org_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(org_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    updated_at=excluded.updated_at
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
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                "SELECT org_id, name, description, created_at, updated_at FROM organizations WHERE org_id = ?",
                (str(org_id or "").strip(),),
            ).fetchone()
        return self._org_from_row(row)

    def list_orgs(self, *, limit: int = 100) -> list[OrganizationRecord]:
        normalized_limit = max(1, min(int(limit or 100), 500))
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT org_id, name, description, created_at, updated_at
                FROM organizations
                ORDER BY updated_at DESC, org_id ASC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()
        return [
            record for row in rows if (record := self._org_from_row(row)) is not None
        ]

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
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, display_name, email, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    email=excluded.email,
                    updated_at=excluded.updated_at
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
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                "SELECT user_id, display_name, email, created_at, updated_at FROM users WHERE user_id = ?",
                (str(user_id or "").strip(),),
            ).fetchone()
        return self._user_from_row(row)

    def list_users(self, *, limit: int = 100) -> list[UserRecord]:
        normalized_limit = max(1, min(int(limit or 100), 500))
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT user_id, display_name, email, created_at, updated_at
                FROM users
                ORDER BY updated_at DESC, user_id ASC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()
        return [
            record for row in rows if (record := self._user_from_row(row)) is not None
        ]

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
        with connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memberships (org_id, user_id, role, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(org_id, user_id) DO UPDATE SET
                    role=excluded.role,
                    updated_at=excluded.updated_at
                """,
                (normalized_org_id, normalized_user_id, normalized_role, now, now),
            )
            conn.commit()
        record = self.get_membership(
            org_id=normalized_org_id, user_id=normalized_user_id
        )
        if record is None:
            raise RuntimeError("failed to set membership")
        return record

    def get_membership(self, *, org_id: str, user_id: str) -> MembershipRecord | None:
        with connect_sqlite(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT org_id, user_id, role, created_at, updated_at
                FROM memberships
                WHERE org_id = ? AND user_id = ?
                """,
                (str(org_id or "").strip(), str(user_id or "").strip()),
            ).fetchone()
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
            clauses.append("org_id = ?")
            values.append(str(org_id or "").strip())
        if str(user_id or "").strip():
            clauses.append("user_id = ?")
            values.append(str(user_id or "").strip())
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_sqlite(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT org_id, user_id, role, created_at, updated_at
                FROM memberships
                {where_sql}
                ORDER BY updated_at DESC, org_id ASC, user_id ASC
                LIMIT ?
                """,
                (*values, normalized_limit),
            ).fetchall()
        return [
            record
            for row in rows
            if (record := self._membership_from_row(row)) is not None
        ]
