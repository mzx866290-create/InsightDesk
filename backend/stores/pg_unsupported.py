"""Explicit placeholders for PostgreSQL stores that are not migrated yet."""

from __future__ import annotations


class PostgresStoreNotImplementedError(NotImplementedError):
    pass


class UnsupportedPostgresStore:
    def __init__(self, store_name: str):
        raise PostgresStoreNotImplementedError(
            f"PostgreSQL adapter for {store_name} is not implemented yet. "
            "Use DATABASE_PROVIDER=sqlite for this store until the adapter is added."
        )
