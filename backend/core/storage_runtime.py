"""Storage runtime configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_SQLITE_DB_PATH = "./chat_history.db"
DATABASE_PROVIDER_SQLITE = "sqlite"
DATABASE_PROVIDER_POSTGRES = "postgres"
SUPPORTED_DATABASE_PROVIDERS = {DATABASE_PROVIDER_SQLITE, DATABASE_PROVIDER_POSTGRES}
VECTOR_STORE_PROVIDER_FAISS = "faiss"
VECTOR_STORE_PROVIDER_QDRANT = "qdrant"
SUPPORTED_VECTOR_STORE_PROVIDERS = {VECTOR_STORE_PROVIDER_FAISS, VECTOR_STORE_PROVIDER_QDRANT}
SUPPORTED_POSTGRES_DSN_SCHEMES = {"postgres", "postgresql"}
SUPPORTED_QDRANT_URL_SCHEMES = {"http", "https"}
STORAGE_MIGRATION_EXECUTE_ENV = "STORAGE_MIGRATION_EXECUTE"
STORAGE_MIGRATION_ROLLBACK_ENV = "STORAGE_MIGRATION_ROLLBACK"
STORAGE_INTEGRATION_TEST_ENV = "STORAGE_INTEGRATION_TEST"


@dataclass(frozen=True)
class StorageValidationSummary:
    """Structured, side-effect-free storage validation payload."""

    kind: str
    provider: str
    configured: bool
    target: dict[str, Any]
    availability: dict[str, Any]
    operations: dict[str, bool]
    warnings: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "provider": self.provider,
            "configured": self.configured,
            "target": self.target,
            "availability": self.availability,
            "operations": self.operations,
            "warnings": list(self.warnings),
            "risks": list(self.risks),
        }


def _safe_path_snapshot(raw_path: str) -> dict[str, Any]:
    normalized = str(raw_path or "").strip()
    if not normalized:
        return {
            "path": "",
            "absolute_path": "",
            "exists": False,
            "is_dir": False,
            "is_file": False,
            "parent": "",
            "parent_exists": False,
            "parent_writable": False,
        }
    if normalized == ":memory:":
        return {
            "path": normalized,
            "absolute_path": normalized,
            "exists": True,
            "is_dir": False,
            "is_file": False,
            "parent": "",
            "parent_exists": True,
            "parent_writable": True,
        }

    target = Path(normalized).expanduser()
    try:
        absolute_path = str(target.resolve(strict=False))
        exists = target.exists()
        is_dir = target.is_dir()
        is_file = target.is_file()
    except OSError:
        absolute_path = str(target)
        exists = False
        is_dir = False
        is_file = False

    parent = target.parent
    try:
        parent_exists = parent.exists()
        parent_writable = parent_exists and os.access(str(parent), os.W_OK)
    except OSError:
        parent_exists = False
        parent_writable = False

    return {
        "path": normalized,
        "absolute_path": absolute_path,
        "exists": exists,
        "is_dir": is_dir,
        "is_file": is_file,
        "parent": str(parent),
        "parent_exists": parent_exists,
        "parent_writable": parent_writable,
    }


def _safe_child_exists(parent_path: str, file_name: str) -> bool:
    try:
        return (Path(parent_path).expanduser() / file_name).is_file()
    except OSError:
        return False


def _redact_dsn(dsn: str) -> str:
    normalized = str(dsn or "").strip()
    if not normalized:
        return ""
    if "@" not in normalized or "://" not in normalized:
        return "<configured>"
    scheme, rest = normalized.split("://", 1)
    if "@" not in rest:
        return f"{scheme}://<configured>"
    _, host_part = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host_part}"


def validate_postgres_config(dsn: str | None = None) -> dict[str, Any]:
    """Validate PostgreSQL config shape without opening a database connection."""

    configured_dsn = postgres_dsn() if dsn is None else str(dsn).strip()
    parsed = urlparse(configured_dsn)
    warnings: list[str] = []

    if not configured_dsn:
        warnings.append("postgres_dsn_missing")
    elif parsed.scheme.lower() not in SUPPORTED_POSTGRES_DSN_SCHEMES:
        warnings.append("postgres_dsn_invalid_scheme")

    configured = bool(configured_dsn)
    valid = configured and not warnings
    return {
        "configured": configured,
        "valid": valid,
        "target": {
            "dsn_configured": configured,
            "dsn_preview": _redact_dsn(configured_dsn),
            "scheme": parsed.scheme.lower() if configured_dsn else "",
        },
        "availability": {
            "available": valid,
            "status": (
                "configured_not_connected"
                if valid
                else "missing_dsn"
                if not configured
                else "invalid_config"
            ),
            "connectivity_checked": False,
        },
        "warnings": tuple(warnings),
    }


def validate_qdrant_config(
    *,
    url: str | None = None,
    collection_name: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Validate Qdrant config shape without creating a Qdrant client."""

    configured_url = qdrant_url() if url is None else str(url).strip()
    configured_collection = (
        qdrant_collection_name()
        if collection_name is None
        else str(collection_name).strip()
    )
    configured_api_key = qdrant_api_key() if api_key is None else str(api_key).strip()
    parsed = urlparse(configured_url)
    warnings: list[str] = []

    if not configured_url:
        warnings.append("qdrant_url_missing")
    elif parsed.scheme.lower() not in SUPPORTED_QDRANT_URL_SCHEMES:
        warnings.append("qdrant_url_invalid_scheme")
    elif not parsed.netloc:
        warnings.append("qdrant_url_missing_host")

    if not configured_collection:
        warnings.append("qdrant_collection_missing")

    configured = bool(configured_url and configured_collection)
    valid = configured and not warnings
    return {
        "configured": configured,
        "valid": valid,
        "target": {
            "url": configured_url,
            "collection_name": configured_collection,
            "api_key_configured": bool(configured_api_key),
        },
        "availability": {
            "available": valid,
            "status": (
                "configured_not_connected"
                if valid
                else "missing_config"
                if not configured
                else "invalid_config"
            ),
            "collection_configured": bool(configured_collection),
            "connectivity_checked": False,
        },
        "warnings": tuple(warnings),
    }


def database_provider() -> str:
    """Return the configured metadata database provider.

    SQLite remains the only implemented provider. Keeping this explicit gives the
    rest of the app a stable boundary for a future PostgreSQL adapter.
    """

    provider = (
        str(os.getenv("DATABASE_PROVIDER") or DATABASE_PROVIDER_SQLITE).strip().lower()
    )
    if provider in {"postgresql", "pg"}:
        return DATABASE_PROVIDER_POSTGRES
    return provider or DATABASE_PROVIDER_SQLITE


def postgres_dsn() -> str:
    return str(
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_DSN")
        or os.getenv("POSTGRES_URL")
        or ""
    ).strip()


def app_database_path(default: str = DEFAULT_SQLITE_DB_PATH) -> str:
    """Return the SQLite database path used by app-level stores."""

    return str(
        os.getenv("APP_DB_PATH")
        or os.getenv("CHAT_HISTORY_DB_PATH")
        or default
        or DEFAULT_SQLITE_DB_PATH
    ).strip()


def ensure_sqlite_parent(db_path: str) -> None:
    """Create the parent directory for a SQLite file path when it is explicit."""

    normalized = str(db_path or "").strip()
    if not normalized or normalized == ":memory:":
        return
    parent = Path(normalized).expanduser().parent
    if str(parent) in {"", "."}:
        return
    parent.mkdir(parents=True, exist_ok=True)


def assert_supported_database_provider() -> str:
    """Validate the configured provider and return it.

    This intentionally fails fast for non-SQLite providers until a concrete
    adapter exists, instead of silently pretending PostgreSQL is supported.
    """

    provider = database_provider()
    if provider not in SUPPORTED_DATABASE_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_DATABASE_PROVIDERS))
        raise RuntimeError(
            f"Unsupported DATABASE_PROVIDER={provider!r}. Supported providers: {supported}."
        )
    return provider


def database_runtime_summary(default: str = DEFAULT_SQLITE_DB_PATH) -> dict[str, Any]:
    """Return a lightweight database configuration summary without connecting."""

    provider = database_provider()
    warnings: list[str] = []
    risks: list[str] = []
    operations = {"delete_supported": False, "clear_supported": False}

    if provider not in SUPPORTED_DATABASE_PROVIDERS:
        warnings.append("unsupported_database_provider")
        return StorageValidationSummary(
            kind="database",
            provider=provider,
            configured=False,
            target={},
            availability={"available": False, "status": "unsupported_provider"},
            operations=operations,
            warnings=tuple(warnings),
            risks=tuple(risks),
        ).to_dict()

    if provider == DATABASE_PROVIDER_POSTGRES:
        config_check = validate_postgres_config()
        warnings.extend(config_check["warnings"])
        risks.append("postgres_store_coverage_is_partial")
        return StorageValidationSummary(
            kind="database",
            provider=provider,
            configured=config_check["configured"],
            target=config_check["target"],
            availability=config_check["availability"],
            operations=operations,
            warnings=tuple(warnings),
            risks=tuple(risks),
        ).to_dict()

    db_path = app_database_path(default)
    snapshot = _safe_path_snapshot(db_path)
    if not snapshot["exists"] and db_path != ":memory:":
        warnings.append("sqlite_database_file_missing")
    if not snapshot["parent_exists"]:
        warnings.append("sqlite_parent_directory_missing")

    return StorageValidationSummary(
        kind="database",
        provider=provider,
        configured=True,
        target=snapshot,
        availability={
            "available": bool(
                snapshot["exists"] or snapshot["parent_exists"] or db_path == ":memory:"
            ),
            "status": (
                "memory"
                if db_path == ":memory:"
                else "file_exists"
                if snapshot["exists"]
                else "file_missing"
            ),
            "connectivity_checked": False,
        },
        operations=operations,
        warnings=tuple(warnings),
        risks=tuple(risks),
    ).to_dict()


def vector_store_provider() -> str:
    provider = str(os.getenv("VECTOR_STORE_PROVIDER") or VECTOR_STORE_PROVIDER_FAISS).strip().lower()
    return provider or VECTOR_STORE_PROVIDER_FAISS


def qdrant_url() -> str:
    return str(os.getenv("QDRANT_URL") or "http://localhost:6333").strip()


def qdrant_api_key() -> str:
    return str(os.getenv("QDRANT_API_KEY") or "").strip()


def qdrant_collection_name(default: str = "insightdesk_kb") -> str:
    return str(os.getenv("QDRANT_COLLECTION") or default or "insightdesk_kb").strip()


def assert_supported_vector_store_provider() -> str:
    provider = vector_store_provider()
    if provider not in SUPPORTED_VECTOR_STORE_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_VECTOR_STORE_PROVIDERS))
        raise RuntimeError(
            f"Unsupported VECTOR_STORE_PROVIDER={provider!r}. Supported providers: {supported}."
        )
    return provider


def vector_store_runtime_summary(
    *,
    provider: str | None = None,
    path: str = "./vector_store",
    collection_name: str | None = None,
    url: str | None = None,
    api_key: str | None = None,
    delete_supported: bool | None = None,
    clear_supported: bool | None = None,
) -> dict[str, Any]:
    """Return a lightweight vector-store validation summary without remote I/O."""

    normalized_provider = str(provider or vector_store_provider()).strip().lower()
    warnings: list[str] = []
    risks: list[str] = []
    operations = {
        "delete_supported": bool(delete_supported)
        if delete_supported is not None
        else normalized_provider in SUPPORTED_VECTOR_STORE_PROVIDERS,
        "clear_supported": bool(clear_supported)
        if clear_supported is not None
        else normalized_provider in SUPPORTED_VECTOR_STORE_PROVIDERS,
    }

    if normalized_provider not in SUPPORTED_VECTOR_STORE_PROVIDERS:
        warnings.append("unsupported_vector_store_provider")
        return StorageValidationSummary(
            kind="vector_store",
            provider=normalized_provider,
            configured=False,
            target={},
            availability={"available": False, "status": "unsupported_provider"},
            operations=operations,
            warnings=tuple(warnings),
            risks=tuple(risks),
        ).to_dict()

    if normalized_provider == VECTOR_STORE_PROVIDER_QDRANT:
        config_check = validate_qdrant_config(
            url=url,
            collection_name=collection_name,
            api_key=api_key,
        )
        warnings.extend(config_check["warnings"])
        if config_check["valid"]:
            warnings.append("qdrant_collection_not_verified")
        risks.append("qdrant_delete_removes_collection")
        return StorageValidationSummary(
            kind="vector_store",
            provider=normalized_provider,
            configured=config_check["configured"],
            target=config_check["target"],
            availability=config_check["availability"],
            operations=operations,
            warnings=tuple(warnings),
            risks=tuple(risks),
        ).to_dict()

    snapshot = _safe_path_snapshot(path)
    index_files = {
        "index.faiss": _safe_child_exists(path, "index.faiss"),
        "index.pkl": _safe_child_exists(path, "index.pkl"),
    }
    index_ready = bool(snapshot["is_dir"] and all(index_files.values()))
    if not snapshot["exists"]:
        warnings.append("faiss_path_missing")
    elif not index_ready:
        warnings.append("faiss_index_files_missing")
    if not snapshot["parent_exists"]:
        warnings.append("faiss_parent_directory_missing")
    risks.append("faiss_load_uses_dangerous_deserialization")

    return StorageValidationSummary(
        kind="vector_store",
        provider=normalized_provider,
        configured=True,
        target=snapshot,
        availability={
            "available": index_ready,
            "status": (
                "ready"
                if index_ready
                else "path_missing"
                if not snapshot["exists"]
                else "index_files_missing"
            ),
            "path_exists": bool(snapshot["exists"]),
            "index_files": index_files,
            "connectivity_checked": False,
        },
        operations=operations,
        warnings=tuple(warnings),
        risks=tuple(risks),
    ).to_dict()


def storage_runtime_payload(
    *,
    vector_store_path: str = "./vector_store",
    vector_provider: str | None = None,
    collection_name: str | None = None,
) -> dict[str, Any]:
    """Return database and vector-store validation summaries for diagnostics."""

    return {
        "database": database_runtime_summary(),
        "vector_store": vector_store_runtime_summary(
            provider=vector_provider,
            path=vector_store_path,
            collection_name=collection_name,
        ),
    }


def _env_flag(name: str) -> bool:
    return str(os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def storage_readiness_contract() -> dict[str, Any]:
    """Return executable readiness gates without touching external services."""

    return {
        "id": "storage_readiness_contract",
        "commands": {
            "offline_preflight": [
                "python",
                "deploy/validate_storage_migration.py",
                "--json",
            ],
            "real_integration": [
                "python",
                "deploy/run_storage_integration_check.py",
            ],
            "execute_migration": [
                "python",
                "deploy/validate_storage_migration.py",
                "--execute",
                "--json",
            ],
        },
        "required_env": {
            "real_integration": [STORAGE_INTEGRATION_TEST_ENV, "DATABASE_URL", "QDRANT_URL"],
            "execute_migration": [
                STORAGE_MIGRATION_EXECUTE_ENV,
                "DATABASE_URL",
                "QDRANT_URL",
            ],
        },
        "gates": {
            STORAGE_INTEGRATION_TEST_ENV: _env_flag(STORAGE_INTEGRATION_TEST_ENV),
            STORAGE_MIGRATION_EXECUTE_ENV: _env_flag(STORAGE_MIGRATION_EXECUTE_ENV),
        },
    }


def storage_rollback_contract() -> dict[str, Any]:
    """Return rollback gates and commands without performing rollback work."""

    return {
        "id": "storage_rollback_contract",
        "commands": {
            "rollback_plan": [
                "python",
                "deploy/validate_storage_migration.py",
                "--rollback-plan",
                "--json",
            ],
            "execute_rollback": [
                "python",
                "deploy/validate_storage_migration.py",
                "--rollback",
                "--json",
            ],
        },
        "required_env": {
            "execute_rollback": [
                STORAGE_MIGRATION_ROLLBACK_ENV,
                "DATABASE_URL",
            ],
        },
        "gates": {
            STORAGE_MIGRATION_ROLLBACK_ENV: _env_flag(STORAGE_MIGRATION_ROLLBACK_ENV),
        },
        "safety": {
            "postgres": "Rollback is destructive and requires --confirm-drop-postgres-adapter-tables.",
            "qdrant": "Qdrant rollback only deletes collections with the insightdesk_test_ prefix unless explicitly confirmed.",
        },
    }
