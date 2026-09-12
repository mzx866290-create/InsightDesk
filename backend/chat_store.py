"""
SQLite-based persistent chat message history
Implements LangChain's BaseChatMessageHistory interface
"""

import sqlite3
import logging
from typing import TYPE_CHECKING, List, Dict, Any, Optional

from backend.core.storage_runtime import (
    DATABASE_PROVIDER_POSTGRES,
    app_database_path,
    database_provider,
)
from backend.stores.sqlite_runtime import connect_sqlite
from backend.stores.chat_messages import env_int as _env_int
from backend.stores.chat_normalization import (
    DEFAULT_WORKSPACE_ID as DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME as DEFAULT_WORKSPACE_NAME,
)
from backend.stores.bookmark_store import (
    create_or_update_bookmark as create_or_update_bookmark,
    delete_bookmark as delete_bookmark,
    get_bookmark as get_bookmark,
    list_bookmarks as list_bookmarks,
)
from backend.stores.prompt_store import (
    DEFAULT_SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT,
    activate_assistant_preset as activate_assistant_preset,
    activate_system_prompt as activate_system_prompt,
    create_assistant_preset as create_assistant_preset,
    create_system_prompt as create_system_prompt,
    delete_assistant_preset as delete_assistant_preset,
    delete_system_prompt as delete_system_prompt,
    get_active_assistant_preset as get_active_assistant_preset,
    get_active_system_prompt as get_active_system_prompt,
    get_all_assistant_presets as get_all_assistant_presets,
    get_all_system_prompts as get_all_system_prompts,
    update_assistant_preset as update_assistant_preset,
    update_system_prompt as update_system_prompt,
)
from backend.stores.message_feedback_store import (
    set_message_feedback as _set_message_feedback,
)
from backend.stores.panel_answer_store import (
    promote_panel_answer as _promote_panel_answer,
)
from backend.stores.retrieval_feedback_store import (
    aggregate_retrieval_feedback_by_source as aggregate_retrieval_feedback_by_source,
    list_retrieval_feedback as list_retrieval_feedback,
    set_retrieval_feedback as set_retrieval_feedback,
)
from backend.stores.session_memory_store import (
    clear_session_memory as clear_session_memory,
    create_session_memory as create_session_memory,
    delete_session_memory as delete_session_memory,
    list_session_memory as list_session_memory,
    pin_session_memory as pin_session_memory,
    update_session_memory as update_session_memory,
)
from backend.stores.session_panel_store import (
    get_session_panels as _get_session_panels,
    replace_session_panels as _replace_session_panels,
    upsert_session_panel as _upsert_session_panel,
)
from backend.stores.session_store import (
    collect_message_search_hits as _collect_message_search_hits_impl,
    delete_session as _delete_session,
    fetch_session_row as _fetch_session_row_impl,
    get_all_sessions as _get_all_sessions,
    get_session as _get_session,
    reorder_sessions as _reorder_sessions,
    session_exists as _session_exists_impl,
    truncate_session_from_answer_group as _truncate_session_from_answer_group,
    update_session_meta as _update_session_meta,
)
from backend.stores.sqlite_chat_history import (
    SQLiteChatMessageHistory as _SQLiteChatMessageHistory,
    prune_session_messages as _prune_session_messages_impl,
)
from backend.stores.workspace_store import (
    activate_workspace as activate_workspace,
    create_workspace as create_workspace,
    delete_workspace as delete_workspace,
    get_workspace as get_workspace,
    list_workspaces as list_workspaces,
    update_workspace as update_workspace,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.stores.protocols import SessionStore

DB_PATH = app_database_path()


def _should_use_postgres_store(db_path: str | None = None) -> bool:
    """Route default runtime calls to PostgreSQL while preserving explicit SQLite paths."""

    normalized_db_path = str(db_path or "").strip()
    return database_provider() == DATABASE_PROVIDER_POSTGRES and normalized_db_path in {
        "",
        DB_PATH,
    }


def _session_store() -> "SessionStore":
    from backend.stores.factory import create_session_store

    return create_session_store()


# Exported constant so api_server can return it to the frontend
CONTEXT_HISTORY_MESSAGES: int = _env_int("CONTEXT_HISTORY_MESSAGES", 16)

class SQLiteChatMessageHistory(_SQLiteChatMessageHistory):
    """Compatibility wrapper that keeps chat_store.connect_sqlite monkeypatchable."""

    def __init__(self, session_id: str, db_path: str | None = None):
        super().__init__(
            session_id=session_id,
            db_path=db_path,
            connect_sqlite_fn=connect_sqlite,
        )


def _prune_session_messages(
    cursor: sqlite3.Cursor,
    session_id: str,
    max_messages: int,
) -> int:
    return _prune_session_messages_impl(cursor, session_id, max_messages)

def _session_exists(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> bool:
    return _session_exists_impl(cursor, session_id)


def _collect_message_search_hits(
    cursor: sqlite3.Cursor,
    normalized_query: str,
    session_ids: set[str],
) -> Dict[str, str]:
    return _collect_message_search_hits_impl(cursor, normalized_query, session_ids)


def _fetch_session_row(
    cursor: sqlite3.Cursor,
    session_id: str,
) -> Optional[tuple[Any, ...]]:
    return _fetch_session_row_impl(cursor, session_id)


def get_all_sessions(
    db_path: str | None = None,
    query: str = "",
    archived: Optional[bool] = None,
    favorite: Optional[bool] = None,
    tag: str = "",
    workspace_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_store().get_all_sessions(
            query=query,
            archived=archived,
            favorite=favorite,
            tag=tag,
            workspace_id=workspace_id,
        )
    return _get_all_sessions(
        db_path=db_path,
        query=query,
        archived=archived,
        favorite=favorite,
        tag=tag,
        workspace_id=workspace_id,
        connect_sqlite_fn=connect_sqlite,
    )


def get_session(
    session_id: str, db_path: str | None = None
) -> Optional[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_store().get_session(session_id)
    return _get_session(
        session_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )

def set_message_feedback(
    session_id: str,
    *,
    feedback_value: int,
    message_id: Optional[int] = None,
    panel_id: str = "",
    answer_group_id: str = "",
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    return _set_message_feedback(
        session_id,
        feedback_value=feedback_value,
        message_id=message_id,
        panel_id=panel_id,
        answer_group_id=answer_group_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def truncate_session_from_answer_group(
    session_id: str,
    *,
    answer_group_id: str,
    content: str,
    images: Optional[List[Dict[str, Any]]] = None,
    files: Optional[List[Dict[str, Any]]] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_store().truncate_session_from_answer_group(
            session_id,
            answer_group_id=answer_group_id,
            content=content,
            images=images,
            files=files,
        )
    return _truncate_session_from_answer_group(
        session_id,
        answer_group_id=answer_group_id,
        content=content,
        images=images,
        files=files,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def update_session_meta(
    session_id: str,
    *,
    title: Optional[str] = None,
    is_archived: Optional[bool] = None,
    is_favorite: Optional[bool] = None,
    is_pinned: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    workspace_id: Optional[str] = None,
    db_path: str | None = None,
) -> Optional[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        if workspace_id is not None:
            normalized_workspace_id = str(workspace_id or "").strip()
            if not normalized_workspace_id:
                raise ValueError("workspace_id 不能为空")
            # Workspaces still use SQLite during the staged PostgreSQL migration.
            if get_workspace(normalized_workspace_id) is None:
                raise ValueError("工作区不存在")
        return _session_store().update_session_meta(
            session_id,
            title=title,
            is_archived=is_archived,
            is_favorite=is_favorite,
            is_pinned=is_pinned,
            tags=tags,
            workspace_id=workspace_id,
        )
    return _update_session_meta(
        session_id,
        title=title,
        is_archived=is_archived,
        is_favorite=is_favorite,
        is_pinned=is_pinned,
        tags=tags,
        workspace_id=workspace_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def reorder_sessions(
    session_ids: List[str],
    *,
    workspace_id: Optional[str] = None,
    db_path: str | None = None,
) -> Dict[str, Any]:
    if _should_use_postgres_store(db_path):
        return _session_store().reorder_sessions(
            session_ids,
            workspace_id=workspace_id,
        )
    return _reorder_sessions(
        session_ids,
        workspace_id=workspace_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def delete_session(session_id: str, db_path: str | None = None) -> None:
    if _should_use_postgres_store(db_path):
        _session_store().delete_session(session_id)
        return
    _delete_session(
        session_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )

def replace_session_panels(
    session_id: str,
    panel_configs: List[Dict[str, Any]],
    db_path: str = DB_PATH,
) -> None:
    _replace_session_panels(
        session_id,
        panel_configs,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def upsert_session_panel(
    session_id: str,
    panel_config: Dict[str, Any],
    db_path: str = DB_PATH,
) -> None:
    _upsert_session_panel(
        session_id,
        panel_config,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def get_session_panels(session_id: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    return _get_session_panels(
        session_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )


def promote_panel_answer(
    session_id: str,
    answer_group_id: str,
    source_panel_id: str,
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    if _should_use_postgres_store(db_path):
        return _session_store().promote_panel_answer(
            session_id,
            answer_group_id,
            source_panel_id,
        )
    return _promote_panel_answer(
        session_id,
        answer_group_id,
        source_panel_id,
        db_path=db_path,
        connect_sqlite_fn=connect_sqlite,
    )
