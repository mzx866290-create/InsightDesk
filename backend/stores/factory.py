"""Store factory boundary for app metadata persistence.

SQLite is the only concrete implementation today. Route composition code should
ask this module for store instances instead of constructing SQLite stores
directly, so a future PostgreSQL adapter can be introduced behind the same
factory surface.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass

from backend.artifact_service import SQLiteArtifactStore
from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    assert_supported_database_provider,
    postgres_dsn,
)
from backend.deck_service import SQLiteDeckStore
from backend.stores.config_store import SQLiteAppConfigStore
from backend.stores.identity_store import SQLiteIdentityStore
from backend.stores.resource_access_store import SQLiteResourceAccessStore
from backend.stores.protocols import (
    AppConfigStore,
    ArtifactStore,
    DeckStore,
    IdentityStore,
    ResourceAccessStore,
    RetrievalFeedbackStore,
    SecurityAuditStore,
    ShareLinkStore,
    SessionMemoryStore,
    SsoSessionStore,
    TaskStore,
)
from backend.stores.security_audit_store import SQLiteSecurityAuditStore
from backend.stores.share_link_store import SQLiteShareLinkStore
from backend.stores.sso_session_store import SQLiteSsoSessionStore
from backend.stores.task_store import SQLiteTaskStore
from backend.stores.pg_artifact_store import PostgresArtifactStore
from backend.stores.pg_chat_store import PostgresChatMessageHistory
from backend.stores.pg_config_store import PostgresAppConfigStore
from backend.stores.pg_deck_store import PostgresDeckStore
from backend.stores.pg_identity_store import PostgresIdentityStore
from backend.stores.pg_resource_access_store import PostgresResourceAccessStore
from backend.stores.pg_retrieval_feedback_store import PostgresRetrievalFeedbackStore
from backend.stores.pg_security_audit_store import PostgresSecurityAuditStore
from backend.stores.pg_session_memory_store import PostgresSessionMemoryStore
from backend.stores.pg_share_link_store import PostgresShareLinkStore
from backend.stores.pg_sso_session_store import PostgresSsoSessionStore
from backend.stores.pg_task_store import PostgresTaskStore


@dataclass(frozen=True)
class StoreFactoryConfig:
    db_path: str
    provider: str = "sqlite"


def store_factory_config() -> StoreFactoryConfig:
    provider = assert_supported_database_provider()
    if provider == DATABASE_PROVIDER_POSTGRES:
        return StoreFactoryConfig(provider=provider, db_path=postgres_dsn())
    return StoreFactoryConfig(provider=provider, db_path=app_database_path())


def create_app_config_store() -> AppConfigStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresAppConfigStore(dsn=config.db_path)
    return SQLiteAppConfigStore(db_path=config.db_path)


def create_chat_message_history(session_id: str):
    """Create a provider-specific chat message history.

    SQLite remains the default runtime. PostgreSQL support is intentionally
    limited to the message history contract implemented by
    ``PostgresChatMessageHistory``.
    """
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresChatMessageHistory(session_id=session_id, dsn=config.db_path)
    from backend.chat_store import SQLiteChatMessageHistory

    signature = inspect.signature(SQLiteChatMessageHistory)
    parameters = signature.parameters
    accepts_db_path_keyword = "db_path" in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if accepts_db_path_keyword:
        return SQLiteChatMessageHistory(session_id=session_id, db_path=config.db_path)

    positional_parameters = [
        parameter
        for parameter in parameters.values()
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ]
    accepts_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in parameters.values()
    )
    if accepts_varargs or len(positional_parameters) >= 2:
        return SQLiteChatMessageHistory(session_id, config.db_path)
    return SQLiteChatMessageHistory(session_id=session_id)


def create_security_audit_store(*, history_limit: int = 2000) -> SecurityAuditStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresSecurityAuditStore(
            dsn=config.db_path,
            history_limit=history_limit,
        )
    return SQLiteSecurityAuditStore(db_path=config.db_path, history_limit=history_limit)


def create_share_link_store() -> ShareLinkStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresShareLinkStore(dsn=config.db_path)
    return SQLiteShareLinkStore(db_path=config.db_path)


def create_sso_session_store() -> SsoSessionStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresSsoSessionStore(dsn=config.db_path)
    return SQLiteSsoSessionStore(db_path=config.db_path)


def create_task_store(*, history_limit: int, ttl_seconds: int) -> TaskStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresTaskStore(
            dsn=config.db_path,
            history_limit=history_limit,
            ttl_seconds=ttl_seconds,
        )
    return SQLiteTaskStore(
        db_path=config.db_path,
        history_limit=history_limit,
        ttl_seconds=ttl_seconds,
    )


def create_session_memory_store() -> SessionMemoryStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresSessionMemoryStore(dsn=config.db_path)
    raise RuntimeError("Session memory factory is only used for PostgreSQL routing.")


def create_retrieval_feedback_store() -> RetrievalFeedbackStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresRetrievalFeedbackStore(dsn=config.db_path)
    raise RuntimeError("Retrieval feedback factory is only used for PostgreSQL routing.")


def create_artifact_store() -> ArtifactStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresArtifactStore(dsn=config.db_path)
    return SQLiteArtifactStore(db_path=config.db_path)


def create_deck_store() -> DeckStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresDeckStore(dsn=config.db_path)
    return SQLiteDeckStore(db_path=config.db_path)


def create_identity_store() -> IdentityStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresIdentityStore(dsn=config.db_path)
    return SQLiteIdentityStore(db_path=config.db_path)


def create_resource_access_store() -> ResourceAccessStore:
    config = store_factory_config()
    if config.provider == DATABASE_PROVIDER_POSTGRES:
        return PostgresResourceAccessStore(dsn=config.db_path)
    return SQLiteResourceAccessStore(db_path=config.db_path)
