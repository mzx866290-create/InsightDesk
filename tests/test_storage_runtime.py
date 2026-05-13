import re

import pytest

import backend.deck_service as deck_service
import backend.doc_pipeline as doc_pipeline
from backend.core import storage_runtime
from backend.doc_pipeline import DocPipeline
from backend.artifact_service import ArtifactRecord
from backend.stores import factory
from backend.stores.pg_artifact_store import PostgresArtifactStore
from backend.stores.pg_chat_store import PostgresChatMessageHistory
from backend.stores.pg_config_store import PostgresAppConfigStore
from backend.stores.pg_deck_store import PostgresDeckStore
from backend.stores.pg_identity_store import PostgresIdentityStore
from backend.stores.pg_resource_access_store import PostgresResourceAccessStore
from backend.stores.pg_retrieval_feedback_store import PostgresRetrievalFeedbackStore
from backend.stores.pg_share_link_store import PostgresShareLinkStore
from backend.stores.pg_session_memory_store import PostgresSessionMemoryStore
from backend.stores.pg_sso_session_store import PostgresSsoSessionStore
from backend.stores.pg_task_store import PostgresTaskStore
from backend.stores.task_store import TaskRecord, TaskStatus
from backend.stores.vector_store import (
    FaissVectorStoreAdapter,
    QdrantVectorStoreAdapter,
    create_vector_store_adapter,
)


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.rowcount = 0
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split()).lower()
        self.rowcount = 0
        self._result = None
        self.state["sql"].append((normalized, params))
        if normalized.startswith("select session_id from sessions"):
            self._result = self.state.setdefault("sessions", {}).get(params[0])
        elif normalized.startswith("select workspace_id from workspaces"):
            workspaces = list(self.state.setdefault("workspaces", {}).values())
            self._result = workspaces[0] if workspaces else None
        elif normalized.startswith("insert into sessions"):
            session_id, created_at, updated_at, title, workspace_id = params
            self.state.setdefault("sessions", {})[session_id] = (
                session_id,
                created_at,
                updated_at,
                title,
                workspace_id,
            )
            self.rowcount = 1
        elif normalized.startswith("insert into messages"):
            if len(params) == 6:
                (
                    session_id,
                    content,
                    timestamp,
                    answer_group_id,
                    images_json,
                    files_json,
                ) = params
                msg_type = "human"
                model_id = ""
                panel_id = ""
                sources_json = "[]"
                workflow_json = "[]"
                token_usage_json = "{}"
                task_id = ""
                task_type = ""
            else:
                (
                    session_id,
                    msg_type,
                    content,
                    timestamp,
                    model_id,
                    panel_id,
                    answer_group_id,
                    images_json,
                    files_json,
                    sources_json,
                    workflow_json,
                    token_usage_json,
                    task_id,
                    task_type,
                ) = params
            message_id = self.state.setdefault("next_message_id", 1)
            self.state["next_message_id"] = message_id + 1
            self.state.setdefault("messages", {})[message_id] = (
                message_id,
                session_id,
                msg_type,
                content,
                model_id,
                panel_id,
                answer_group_id,
                images_json,
                files_json,
                sources_json,
                workflow_json,
                token_usage_json,
                task_id,
                task_type,
                0,
                timestamp,
            )
            self._result = (message_id,)
            self.rowcount = 1
        elif (
            normalized.startswith("select id from messages")
            or normalized.startswith("select id, coalesce")
        ) and "from messages" in normalized:
            if "and id = %s" in normalized:
                session_id, message_id = params
                rows = [
                    row
                    for row in self.state.setdefault("messages", {}).values()
                    if row[1] == session_id and row[0] == int(message_id) and row[2] == "ai"
                ]
                rows.sort(key=lambda row: row[0], reverse="order by id desc" in normalized)
                self._result = (rows[0][0], rows[0][5], rows[0][6]) if rows else None
            elif "and type = 'ai'" in normalized:
                session_id, panel_id, answer_group_id = params
                rows = [
                    row
                    for row in self.state.setdefault("messages", {}).values()
                    if row[1] == session_id
                    and row[2] == "ai"
                    and row[5] == panel_id
                    and row[6] == answer_group_id
                ]
                rows.sort(key=lambda row: row[0], reverse=True)
                self._result = (rows[0][0], rows[0][5], rows[0][6]) if rows else None
            else:
                session_id, answer_group_id = params
                rows = [
                    row
                    for row in self.state.setdefault("messages", {}).values()
                    if row[1] == session_id
                    and row[2] == "human"
                    and row[5] == ""
                    and row[6] == answer_group_id
                ]
                rows.sort(key=lambda row: row[0])
                self._result = (rows[0][0],) if rows else None
        elif normalized.startswith("update messages set content"):
            content, images_json, files_json, timestamp, message_id = params
            row = self.state.setdefault("messages", {}).get(message_id)
            if row:
                self.state["messages"][message_id] = (
                    row[0],
                    row[1],
                    row[2],
                    content,
                    row[4],
                    row[5],
                    row[6],
                    images_json,
                    files_json,
                    row[9],
                    row[10],
                    row[11],
                    row[12],
                    row[13],
                    row[14],
                    timestamp,
                )
                self.rowcount = 1
        elif normalized.startswith("update messages set feedback_value"):
            feedback_value, message_id = params
            row = self.state.setdefault("messages", {}).get(message_id)
            if row:
                self.state["messages"][message_id] = (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[10],
                    row[11],
                    row[12],
                    row[13],
                    int(feedback_value),
                    row[15],
                )
                self.rowcount = 1
        elif normalized.startswith("insert into message_search"):
            rowid, session_id, content = params
            self.state.setdefault("message_search", {})[rowid] = (
                rowid,
                session_id,
                content,
            )
            self.rowcount = 1
        elif normalized.startswith("select title from sessions"):
            row = self.state.setdefault("sessions", {}).get(params[0])
            self._result = (row[3],) if row else None
        elif normalized.startswith("update sessions set updated_at = %s, title = %s"):
            updated_at, title, session_id = params
            row = self.state.setdefault("sessions", {}).get(session_id)
            if row:
                self.state["sessions"][session_id] = (
                    row[0],
                    row[1],
                    updated_at,
                    title,
                    row[4],
                )
                self.rowcount = 1
        elif normalized.startswith("update sessions set updated_at"):
            updated_at, session_id = params
            row = self.state.setdefault("sessions", {}).get(session_id)
            if row:
                self.state["sessions"][session_id] = (
                    row[0],
                    row[1],
                    updated_at,
                    row[3],
                    row[4],
                )
                self.rowcount = 1
        elif normalized.startswith("select panel_id from session_panels"):
            rows = [
                row
                for row in self.state.setdefault("session_panels", {}).values()
                if row[0] == params[0]
            ]
            rows.sort(key=lambda row: (-int(row[2] or 0), int(row[3] or 0), row[4]))
            self._result = (rows[0][1],) if rows else None
        elif normalized.startswith("select id, type, content"):
            rows = [
                row
                for row in self.state.setdefault("messages", {}).values()
                if row[1] == params[0]
            ]
            if "coalesce(panel_id, '') = '' or coalesce(panel_id, '') = %s" in normalized:
                panel_id = params[1]
                rows = [row for row in rows if row[5] in {"", panel_id}]
                if "not ( type = 'ai'" in normalized:
                    excluded_panel_id = params[2]
                    excluded_group_id = params[3]
                    rows = [
                        row
                        for row in rows
                        if not (
                            row[2] == "ai"
                            and row[5] == excluded_panel_id
                            and row[6] == excluded_group_id
                        )
                    ]
            rows.sort(key=lambda row: row[0])
            self._result = [
                (
                    row[0],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[10],
                    row[11],
                    row[12],
                    row[13],
                    row[14],
                    row[15],
                )
                for row in rows
            ]
        elif normalized.startswith("select m.id, m.type, m.content"):
            session_id, like_query, limit = params
            needle = str(like_query).strip("%").lower()
            rows = []
            for rowid, search_row in self.state.setdefault("message_search", {}).items():
                if search_row[1] != session_id or needle not in search_row[2].lower():
                    continue
                message_row = self.state.setdefault("messages", {}).get(rowid)
                if message_row:
                    rows.append((message_row[0], message_row[2], message_row[3], message_row[15]))
            rows.sort(key=lambda row: row[0], reverse=True)
            self._result = rows[:limit]
        elif normalized.startswith("delete from message_search"):
            value = params[0]
            if isinstance(value, list):
                keys = [
                    key
                    for key in self.state.setdefault("message_search", {})
                    if key in value
                ]
            else:
                keys = [
                    key
                    for key, row in self.state.setdefault("message_search", {}).items()
                    if row[1] == value
                ]
            for key in keys:
                self.state["message_search"].pop(key, None)
            self.rowcount = len(keys)
        elif normalized.startswith("delete from messages") and "returning id" in normalized:
            session_id, panel_id, answer_group_id = params
            keys = [
                key
                for key, row in self.state.setdefault("messages", {}).items()
                if row[1] == session_id
                and row[2] == "ai"
                and row[5] == panel_id
                and row[6] == answer_group_id
            ]
            self._result = [(key,) for key in keys]
            for key in keys:
                self.state["messages"].pop(key, None)
            self.rowcount = len(keys)
        elif normalized.startswith("delete from messages where session_id"):
            session_id = params[0]
            keys = [
                key
                for key, row in self.state.setdefault("messages", {}).items()
                if row[1] == session_id
            ]
            for key in keys:
                self.state["messages"].pop(key, None)
            self.rowcount = len(keys)
        elif normalized.startswith("insert into app_config"):
            key, value, updated_at = params
            self.state["app_config"][key] = (key, value, updated_at)
            self.rowcount = 1
        elif normalized.startswith("select key, value, updated_at from app_config"):
            self._result = self.state["app_config"].get(params[0])
        elif normalized.startswith("delete from app_config"):
            self.rowcount = 1 if self.state["app_config"].pop(params[0], None) else 0
        elif normalized.startswith("insert into artifacts"):
            (
                artifact_id,
                session_id,
                artifact_type,
                title,
                status,
                linked_resource_type,
                linked_resource_id,
                content_json,
                created_at,
                updated_at,
            ) = params
            existing = self.state.setdefault("artifacts", {}).get(artifact_id)
            self.state["artifacts"][artifact_id] = (
                artifact_id,
                session_id,
                artifact_type,
                title,
                status,
                linked_resource_type,
                linked_resource_id,
                content_json,
                existing[8] if existing else created_at,
                updated_at,
            )
        elif normalized.startswith("select artifact_id, session_id"):
            self._result = self.state.setdefault("artifacts", {}).get(params[0])
        elif normalized.startswith("select artifact_id from artifacts"):
            rows = list(self.state.setdefault("artifacts", {}).values())
            if "where session_id" in normalized:
                rows = [row for row in rows if row[1] == params[0]]
            elif "where artifact_type" in normalized:
                rows = [row for row in rows if row[2] == params[0]]
            elif "where linked_resource_type" in normalized:
                rows = [row for row in rows if row[5] == params[0] and row[6] == params[1]]
            self._result = [(row[0],) for row in rows]
        elif normalized.startswith("delete from artifacts"):
            session_id = params[0]
            artifact_ids = [
                artifact_id
                for artifact_id, row in self.state.setdefault("artifacts", {}).items()
                if row[1] == session_id
            ]
            for artifact_id in artifact_ids:
                self.state["artifacts"].pop(artifact_id, None)
            self.rowcount = len(artifact_ids)
        elif normalized.startswith("insert into decks"):
            deck_id, session_id, title, spec_json, created_at, updated_at = params
            existing = self.state.setdefault("decks", {}).get(deck_id)
            self.state["decks"][deck_id] = (
                deck_id,
                session_id,
                title,
                spec_json,
                existing[4] if existing else created_at,
                updated_at,
            )
        elif normalized.startswith("select spec_json from decks"):
            row = self.state.setdefault("decks", {}).get(params[0])
            self._result = (row[3],) if row else None
        elif normalized.startswith("select deck_id from decks"):
            rows = list(self.state.setdefault("decks", {}).values())
            if "where session_id" in normalized:
                rows = [row for row in rows if row[1] == params[0]]
            self._result = [(row[0],) for row in rows]
        elif normalized.startswith("delete from decks"):
            session_id = params[0]
            deck_ids = [
                deck_id
                for deck_id, row in self.state.setdefault("decks", {}).items()
                if row[1] == session_id
            ]
            for deck_id in deck_ids:
                self.state["decks"].pop(deck_id, None)
            self.rowcount = len(deck_ids)
        elif normalized.startswith("insert into tasks"):
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
            ) = params
            self.state["tasks"][task_id] = (
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
            )
        elif normalized.startswith("select created_at from attachment_promotions"):
            promotion = self.state.setdefault("attachment_promotions", {}).get(
                (params[0], params[1])
            )
            self._result = (promotion[6],) if promotion else None
        elif normalized.startswith("insert into attachment_promotions"):
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
            ) = params
            self.state.setdefault("attachment_promotions", {})[
                (attachment_id, vector_store_path)
            ] = (
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
            )
        elif normalized.startswith("select task_id, task_type"):
            if "where task_id" in normalized:
                self._result = self.state["tasks"].get(params[0])
            elif "where session_id" in normalized:
                self._result = [
                    row for row in self.state["tasks"].values() if row[4] == params[0]
                ]
            else:
                self._result = list(self.state["tasks"].values())
        elif normalized.startswith("select attachment_id, vector_store_path"):
            self._result = self.state.setdefault("attachment_promotions", {}).get(
                (params[0], params[1])
            )
        elif normalized.startswith("delete from tasks where session_id"):
            session_id = params[0]
            task_ids = [
                task_id
                for task_id, row in self.state["tasks"].items()
                if row[4] == session_id
            ]
            for task_id in task_ids:
                self.state["tasks"].pop(task_id, None)
            self.rowcount = len(task_ids)
        elif normalized.startswith("delete from attachment_promotions where session_id"):
            session_id = params[0]
            promotion_keys = [
                key
                for key, row in self.state.setdefault(
                    "attachment_promotions", {}
                ).items()
                if row[5] == session_id
            ]
            for key in promotion_keys:
                self.state["attachment_promotions"].pop(key, None)
            self.rowcount = len(promotion_keys)
        elif normalized.startswith("insert into resource_grants"):
            (
                resource_type,
                resource_id,
                subject_type,
                subject_id,
                role,
                created_at,
                updated_at,
            ) = params
            key = (resource_type, resource_id, subject_type, subject_id)
            existing = self.state.setdefault("resource_grants", {}).get(key)
            self.state["resource_grants"][key] = (
                resource_type,
                resource_id,
                subject_type,
                subject_id,
                role,
                existing[5] if existing else created_at,
                updated_at,
            )
        elif normalized.startswith("select resource_type, resource_id"):
            rows = list(self.state.setdefault("resource_grants", {}).values())
            if "where resource_type = %s and resource_id = %s and subject_type = %s and subject_id = %s" in normalized:
                key = (params[0], params[1], params[2], params[3])
                self._result = self.state["resource_grants"].get(key)
            else:
                index_by_column = {
                    "resource_type": 0,
                    "resource_id": 1,
                    "subject_type": 2,
                    "subject_id": 3,
                    "role": 4,
                }
                filter_columns = [
                    column
                    for column in index_by_column
                    if f"{column} = %s" in normalized
                ]
                filter_values = params[: len(filter_columns)]
                for column, value in zip(filter_columns, filter_values):
                    rows = [
                        row
                        for row in rows
                        if row[index_by_column[column]] == value
                    ]
                self._result = rows
        elif normalized.startswith("select count(*) from resource_grants"):
            rows = list(self.state.setdefault("resource_grants", {}).values())
            if "role = %s" in normalized:
                rows = [row for row in rows if row[4] == params[0]]
            self._result = (len(rows),)
        elif normalized.startswith("delete from resource_grants"):
            key = (params[0], params[1], params[2], params[3])
            self.rowcount = 1 if self.state.setdefault("resource_grants", {}).pop(key, None) else 0
        elif normalized.startswith("insert into organizations"):
            org_id, name, description, created_at, updated_at = params
            existing = self.state.setdefault("organizations", {}).get(org_id)
            self.state["organizations"][org_id] = (
                org_id,
                name,
                description,
                existing[3] if existing else created_at,
                updated_at,
            )
        elif normalized.startswith("select org_id, name"):
            rows = list(self.state.setdefault("organizations", {}).values())
            if "where org_id" in normalized:
                self._result = self.state["organizations"].get(params[0])
            else:
                self._result = rows
        elif normalized.startswith("insert into users"):
            user_id, display_name, email, created_at, updated_at = params
            existing = self.state.setdefault("users", {}).get(user_id)
            self.state["users"][user_id] = (
                user_id,
                display_name,
                email,
                existing[3] if existing else created_at,
                updated_at,
            )
        elif normalized.startswith("select user_id, display_name"):
            rows = list(self.state.setdefault("users", {}).values())
            if "where user_id" in normalized:
                self._result = self.state["users"].get(params[0])
            else:
                self._result = rows
        elif normalized.startswith("insert into memberships"):
            org_id, user_id, role, created_at, updated_at = params
            key = (org_id, user_id)
            existing = self.state.setdefault("memberships", {}).get(key)
            self.state["memberships"][key] = (
                org_id,
                user_id,
                role,
                existing[3] if existing else created_at,
                updated_at,
            )
        elif normalized.startswith("select org_id, user_id"):
            rows = list(self.state.setdefault("memberships", {}).values())
            if "where org_id = %s and user_id = %s" in normalized:
                self._result = self.state["memberships"].get((params[0], params[1]))
            else:
                if "org_id = %s" in normalized:
                    rows = [row for row in rows if row[0] == params[0]]
                if "user_id = %s" in normalized:
                    filter_value = params[0] if "org_id = %s" not in normalized else params[1]
                    rows = [row for row in rows if row[1] == filter_value]
                self._result = rows
        elif normalized.startswith("insert into share_links"):
            (
                share_token,
                resource_type,
                resource_id,
                created_at,
                expires_at,
                created_by_ip,
                created_user_agent,
            ) = params
            existing = self.state.setdefault("share_links", {}).get(share_token)
            self.state["share_links"][share_token] = (
                share_token,
                resource_type,
                resource_id,
                existing[3] if existing else created_at,
                expires_at,
                None,
                created_by_ip,
                created_user_agent,
                existing[8] if existing else 0,
                existing[9] if existing else None,
                existing[10] if existing else "",
                existing[11] if existing else "",
            )
        elif normalized.startswith("select share_token"):
            rows = list(self.state.setdefault("share_links", {}).values())
            if "where share_token" in normalized:
                self._result = self.state["share_links"].get(params[0])
            elif "where resource_type" in normalized:
                self._result = [row for row in rows if row[1] == params[0]]
            else:
                self._result = rows
        elif normalized.startswith("update share_links set revoked_at"):
            row = self.state.setdefault("share_links", {}).get(params[1])
            if row:
                self.state["share_links"][params[1]] = (*row[:5], row[5] or params[0], *row[6:])
                self.rowcount = 1
        elif normalized.startswith("update share_links set access_count"):
            row = self.state.setdefault("share_links", {}).get(params[3])
            if row:
                self.state["share_links"][params[3]] = (
                    *row[:8],
                    int(row[8] or 0) + 1,
                    params[0],
                    params[1],
                    params[2],
                )
                self.rowcount = 1
        elif normalized.startswith("delete from share_links"):
            keys = [
                key
                for key, row in self.state.setdefault("share_links", {}).items()
                if row[1] == params[0] and row[2] == params[1]
            ]
            for key in keys:
                self.state["share_links"].pop(key, None)
            self.rowcount = len(keys)
        elif normalized.startswith("insert into sso_sessions"):
            self.state.setdefault("sso_sessions", {})[params[0]] = tuple(params)
        elif normalized.startswith("select token_hash"):
            self._result = self.state.setdefault("sso_sessions", {}).get(params[0])
        elif normalized.startswith("delete from sso_sessions where token_hash"):
            self.rowcount = 1 if self.state.setdefault("sso_sessions", {}).pop(params[0], None) else 0
        elif normalized.startswith("delete from sso_sessions where expires_at"):
            keys = [
                key
                for key, row in self.state.setdefault("sso_sessions", {}).items()
                if row[5] <= params[0]
            ]
            for key in keys:
                self.state["sso_sessions"].pop(key, None)
            self.rowcount = len(keys)
        return self

    def fetchone(self):
        return self._result

    def fetchall(self):
        if isinstance(self._result, list):
            return self._result
        return []


class FakeConnection:
    def __init__(self, state):
        self.state = state
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursor(self.state)

    def commit(self):
        self.commits += 1


def fake_connection_factory(state):
    return lambda: FakeConnection(state)


def test_storage_runtime_normalizes_database_and_vector_providers(monkeypatch):
    monkeypatch.setenv("DATABASE_PROVIDER", "postgresql")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")

    assert storage_runtime.database_provider() == "postgres"
    assert storage_runtime.vector_store_provider() == "qdrant"
    assert storage_runtime.assert_supported_database_provider() == "postgres"
    assert storage_runtime.assert_supported_vector_store_provider() == "qdrant"


def test_factory_selects_postgres_app_config_and_task_store(monkeypatch):
    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    monkeypatch.setattr(PostgresAppConfigStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresArtifactStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresChatMessageHistory, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresChatMessageHistory, "_ensure_session_exists", lambda self: None)
    monkeypatch.setattr(PostgresDeckStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresIdentityStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresResourceAccessStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresRetrievalFeedbackStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresShareLinkStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresSessionMemoryStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresSsoSessionStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresTaskStore, "_init_db", lambda self: None)
    monkeypatch.setattr(PostgresTaskStore, "_fail_incomplete_tasks", lambda self: None)
    monkeypatch.setattr(PostgresTaskStore, "prune", lambda self, **kwargs: None)

    config = factory.store_factory_config()

    assert config.provider == "postgres"
    assert config.db_path == "postgresql://example/db"
    assert isinstance(factory.create_app_config_store(), PostgresAppConfigStore)
    assert isinstance(factory.create_chat_message_history("session-1"), PostgresChatMessageHistory)
    assert isinstance(factory.create_task_store(history_limit=5, ttl_seconds=10), PostgresTaskStore)
    assert isinstance(factory.create_artifact_store(), PostgresArtifactStore)
    assert isinstance(factory.create_deck_store(), PostgresDeckStore)
    assert isinstance(factory.create_resource_access_store(), PostgresResourceAccessStore)
    assert isinstance(factory.create_identity_store(), PostgresIdentityStore)
    assert isinstance(factory.create_share_link_store(), PostgresShareLinkStore)
    assert isinstance(factory.create_sso_session_store(), PostgresSsoSessionStore)
    assert isinstance(factory.create_session_memory_store(), PostgresSessionMemoryStore)
    assert isinstance(
        factory.create_retrieval_feedback_store(),
        PostgresRetrievalFeedbackStore,
    )


def test_factory_keeps_sqlite_chat_history_as_default(monkeypatch, tmp_path):
    import backend.chat_store as chat_store

    db_path = tmp_path / "chat_history.db"
    monkeypatch.delenv("DATABASE_PROVIDER", raising=False)
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    history = factory.create_chat_message_history("session-sqlite-default")

    assert isinstance(history, chat_store.SQLiteChatMessageHistory)
    assert history.db_path == str(db_path)


def test_chat_store_routes_session_memory_and_panels_to_postgres(monkeypatch):
    import backend.chat_store as chat_store

    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")

    class FakeSessionMemoryStore:
        def __init__(self):
            self.calls = []

        def list_session_memory(self, session_id, **kwargs):
            self.calls.append(("list", session_id, kwargs))
            return [{"id": "mem-1"}]

        def create_session_memory(self, session_id, **kwargs):
            self.calls.append(("create", session_id, kwargs))
            return {"id": "mem-2"}

        def pin_session_memory(self, session_id, **kwargs):
            self.calls.append(("pin", session_id, kwargs))
            return {"created": True, "memory": {"id": "mem-3"}}

        def update_session_memory(self, session_id, memory_id, **kwargs):
            self.calls.append(("update", session_id, memory_id, kwargs))
            return {"id": memory_id}

        def delete_session_memory(self, session_id, memory_id):
            self.calls.append(("delete", session_id, memory_id))
            return True

        def clear_session_memory(self, session_id):
            self.calls.append(("clear", session_id))

        def replace_session_panels(self, session_id, panel_configs):
            self.calls.append(("replace_panels", session_id, panel_configs))

        def upsert_session_panel(self, session_id, panel_config):
            self.calls.append(("upsert_panel", session_id, panel_config))

        def get_session_panels(self, session_id):
            self.calls.append(("get_panels", session_id))
            return [{"panel_id": "panel-main"}]

    store = FakeSessionMemoryStore()
    monkeypatch.setattr(factory, "create_session_memory_store", lambda: store)

    assert chat_store.list_session_memory(
        "session-1",
        kind="fact",
        limit=5,
        newest_first=True,
    ) == [{"id": "mem-1"}]
    assert chat_store.create_session_memory(
        "session-1",
        kind="todo",
        content="remember",
        meta={"source": "test"},
    ) == {"id": "mem-2"}
    assert chat_store.pin_session_memory(
        "session-1",
        content="remember",
        kind="decision",
    )["memory"]["id"] == "mem-3"
    assert chat_store.update_session_memory(
        "session-1",
        "mem-1",
        content="updated",
    ) == {"id": "mem-1"}
    assert chat_store.delete_session_memory("session-1", "mem-1") is True
    chat_store.clear_session_memory("session-1")
    chat_store.replace_session_panels("session-1", [{"panel_id": "panel-main"}])
    chat_store.upsert_session_panel("session-1", {"panel_id": "panel-side"})
    assert chat_store.get_session_panels("session-1") == [{"panel_id": "panel-main"}]

    assert ("list", "session-1", {"kind": "fact", "limit": 5, "newest_first": True}) in store.calls
    assert (
        "update",
        "session-1",
        "mem-1",
        {
            "content": "updated",
            "kind": None,
            "meta": None,
            "update_content": True,
            "update_kind": False,
            "update_meta": False,
        },
    ) in store.calls
    assert ("get_panels", "session-1") in store.calls


def test_chat_store_routes_retrieval_feedback_to_postgres(monkeypatch):
    import backend.chat_store as chat_store

    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")

    class FakeRetrievalFeedbackStore:
        def __init__(self):
            self.calls = []

        def set_retrieval_feedback(self, session_id, **kwargs):
            self.calls.append(("set", session_id, kwargs))
            return {"source_key": "doc:1", "feedback_value": 1}

        def list_retrieval_feedback(self, session_id, **kwargs):
            self.calls.append(("list", session_id, kwargs))
            return [{"source_key": "doc:1"}]

        def aggregate_retrieval_feedback_by_source(self, **kwargs):
            self.calls.append(("aggregate", kwargs))
            return [{"source_title": "Doc"}]

    store = FakeRetrievalFeedbackStore()
    monkeypatch.setattr(factory, "create_retrieval_feedback_store", lambda: store)

    assert chat_store.set_retrieval_feedback(
        "session-1",
        panel_id="panel-main",
        answer_group_id="answer-1",
        source={"type": "document", "title": "Doc"},
        feedback_value=1,
    ) == {"source_key": "doc:1", "feedback_value": 1}
    assert chat_store.list_retrieval_feedback(
        "session-1",
        panel_id="panel-main",
        answer_group_id="answer-1",
    ) == [{"source_key": "doc:1"}]
    assert chat_store.aggregate_retrieval_feedback_by_source(
        source_type="document",
    ) == [{"source_title": "Doc"}]

    assert store.calls == [
        (
            "set",
            "session-1",
            {
                "panel_id": "panel-main",
                "answer_group_id": "answer-1",
                "source": {"type": "document", "title": "Doc"},
                "feedback_value": 1,
            },
        ),
        (
            "list",
            "session-1",
            {"panel_id": "panel-main", "answer_group_id": "answer-1"},
        ),
        ("aggregate", {"source_type": "document"}),
    ]


def test_chat_store_routes_message_feedback_to_postgres(monkeypatch):
    import backend.chat_store as chat_store

    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")

    class FakeHistory:
        def __init__(self):
            self.calls = []

        def set_message_feedback(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "message_id": 42,
                "panel_id": kwargs["panel_id"],
                "answer_group_id": kwargs["answer_group_id"],
                "feedback_value": kwargs["feedback_value"],
            }

    history = FakeHistory()
    monkeypatch.setattr(factory, "create_chat_message_history", lambda session_id: history)

    assert chat_store.set_message_feedback(
        "session-1",
        feedback_value=1,
        panel_id="panel-main",
        answer_group_id="answer-1",
    ) == {
        "message_id": 42,
        "panel_id": "panel-main",
        "answer_group_id": "answer-1",
        "feedback_value": 1,
    }
    assert history.calls == [
        {
            "feedback_value": 1,
            "message_id": None,
            "panel_id": "panel-main",
            "answer_group_id": "answer-1",
        }
    ]


def test_phase_summary_memory_uses_postgres_history_without_sqlite_db_path(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    import backend.chat_store as chat_store
    from backend.core import session_summary_runtime

    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")

    class FakeHistory:
        db_path = "postgresql://example/db"

        def get_all_message_records(self):
            return [{"type": "human"}, {"type": "ai"}]

    calls = {"list": [], "pin": []}

    def fake_list_session_memory(session_id, **kwargs):
        calls["list"].append((session_id, kwargs))
        return []

    def fake_pin_session_memory(session_id, **kwargs):
        calls["pin"].append((session_id, kwargs))
        return {
            "id": "summary-1",
            "session_id": session_id,
            "kind": kwargs["kind"],
            "content": kwargs["content"],
            "meta": kwargs["meta"],
            "created": True,
        }

    monkeypatch.setattr(factory, "create_chat_message_history", lambda session_id: FakeHistory())
    monkeypatch.setattr(chat_store, "list_session_memory", fake_list_session_memory)
    monkeypatch.setattr(chat_store, "pin_session_memory", fake_pin_session_memory)

    ctx = SimpleNamespace(
        SESSION_MEMORY_AUTO_SUMMARY_MIN_TURNS=2,
        SESSION_MEMORY_AUTO_SUMMARY_MIN_NEW_TURNS=1,
        SESSION_MEMORY_AUTO_SUMMARY_WINDOW_SIZE=4,
        SESSION_MEMORY_AUTO_SUMMARY_MAX_CONTENT_CHARS=1000,
        re=re,
        summary_turns=lambda records, clip_text: [
            {"user": "u1", "assistant": "a1"},
            {"user": "u2", "assistant": "a2"},
        ],
        latest_auto_summary=lambda summaries: None,
        covered_turns_from_summary=lambda summary: 0,
        build_phase_summary_content=lambda turns, **kwargs: "summary text",
        summary_llm_enabled=lambda: False,
        summarize_window_meta=lambda **kwargs: {"source": "auto", **kwargs},
    )

    result = asyncio.run(
        session_summary_runtime._generate_session_phase_summary_memory(
            ctx,
            "session-1",
            trigger="manual_api",
        )
    )

    assert result is not None
    assert result["created"] is True
    assert calls["list"] == [("session-1", {"kind": "summary", "newest_first": True})]
    assert calls["pin"][0][0] == "session-1"
    assert "db_path" not in calls["pin"][0][1]


def test_postgres_app_config_store_roundtrip_with_fake_connection(monkeypatch, tmp_path):
    state = {"sql": [], "app_config": {}, "tasks": {}}
    monkeypatch.setenv("APP_CONFIG_MASTER_KEY_PATH", str(tmp_path / ".key"))
    store = PostgresAppConfigStore(
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )

    saved = store.set("tavily_api_key", "secret")
    loaded = store.get("tavily_api_key")

    assert saved.value == "secret"
    assert loaded is not None
    assert loaded.value == "secret"
    assert state["app_config"]["tavily_api_key"][1] != "secret"
    assert store.delete("tavily_api_key") is True


def test_postgres_chat_message_history_add_get_clear_and_search_with_fake_connection():
    state = {
        "sql": [],
        "sessions": {},
        "workspaces": {
            "workspace-default": (
                "workspace-default",
                "Default",
                1,
                1.0,
                1.0,
            )
        },
        "session_panels": {},
        "messages": {},
        "message_search": {},
    }
    store = PostgresChatMessageHistory(
        session_id="session-1",
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )

    store.add_user_message("Need alpha search", answer_group_id="turn-1")
    store.add_ai_message(
        "Alpha answer",
        model_id="model-a",
        panel_id="panel-main",
        answer_group_id="turn-1",
        sources=[{"title": "Doc"}],
        token_usage={
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
            "estimated": False,
        },
    )
    all_messages = store.get_all_messages()
    records = store.get_all_message_records()
    hits = store.search_messages("alpha")
    store.clear()

    assert [message.content for message in all_messages] == [
        "Need alpha search",
        "Alpha answer",
    ]
    assert records[1]["model_id"] == "model-a"
    assert records[1]["sources"] == [{"title": "Doc"}]
    assert records[1]["token_usage"]["total_tokens"] == 14
    assert [hit["content"] for hit in hits] == ["Alpha answer", "Need alpha search"]
    assert state["messages"] == {}
    assert state["message_search"] == {}


def test_postgres_chat_message_history_rerun_helpers_with_fake_connection():
    state = {
        "sql": [],
        "sessions": {},
        "workspaces": {
            "workspace-default": (
                "workspace-default",
                "Default",
                1,
                1.0,
                1.0,
            )
        },
        "session_panels": {},
        "messages": {},
        "message_search": {},
    }
    store = PostgresChatMessageHistory(
        session_id="session-1",
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )

    store.add_user_message_once("Original question", answer_group_id="turn-1")
    store.add_user_message_once("Updated question", answer_group_id="turn-1")
    store.add_ai_message(
        "Old panel answer",
        panel_id="panel-main",
        answer_group_id="turn-1",
    )
    store.add_ai_message(
        "Other panel answer",
        panel_id="panel-side",
        answer_group_id="turn-1",
    )
    feedback = store.set_message_feedback(
        feedback_value=1,
        panel_id="panel-main",
        answer_group_id="turn-1",
    )
    assert state["messages"][2][14] == 1

    rerun_messages = store.get_panel_messages_for_rerun(
        "panel-main",
        "turn-1",
    )
    store.delete_ai_messages_for_answer_group("panel-main", "turn-1")
    records = store.get_all_message_records()
    hits = store.search_messages("updated")

    assert [message.content for message in rerun_messages] == ["Updated question"]
    assert [record["content"] for record in records] == [
        "Updated question",
        "Other panel answer",
    ]
    assert [hit["content"] for hit in hits] == ["Updated question"]
    assert feedback == {
        "message_id": 2,
        "panel_id": "panel-main",
            "answer_group_id": "turn-1",
            "feedback_value": 1,
        }
    assert len(
        [
            row
            for row in state["messages"].values()
            if row[2] == "human" and row[6] == "turn-1"
        ]
    ) == 1


def test_postgres_task_store_save_get_and_list_with_fake_connection():
    state = {"sql": [], "app_config": {}, "tasks": {}, "attachment_promotions": {}}
    store = PostgresTaskStore(
        dsn="postgresql://example/db",
        history_limit=5,
        ttl_seconds=10,
        connection_factory=fake_connection_factory(state),
    )
    record = TaskRecord(
        task_id="task-1",
        task_type="demo",
        status=TaskStatus.COMPLETED,
        params={"x": 1},
        session_id="session-1",
        created_at=1.0,
        updated_at=2.0,
        result="done",
        progress=100,
    )

    store.save(record)
    loaded = store.get("task-1")
    recent = store.list_recent(limit=5)

    assert loaded is not None
    assert loaded.task_id == "task-1"
    assert loaded.params == {"x": 1}
    assert recent[0].task_id == "task-1"


def test_postgres_task_store_handles_promotions_and_session_delete_with_fake_connection():
    state = {"sql": [], "app_config": {}, "tasks": {}, "attachment_promotions": {}}
    store = PostgresTaskStore(
        dsn="postgresql://example/db",
        history_limit=5,
        ttl_seconds=10,
        connection_factory=fake_connection_factory(state),
    )
    record = TaskRecord(
        task_id="promotion-task",
        task_type="promote_attachment_to_kb",
        status=TaskStatus.COMPLETED,
        params={
            "attachment_id": "attachment-1",
            "attachment_name": "source.pdf",
            "vector_store_path": "kb-main",
        },
        session_id="session-1",
        created_at=1.0,
        updated_at=2.0,
        result="done",
        progress=100,
    )

    store.save(record)
    promotion = store.get_attachment_promotion("attachment-1", "kb-main")
    deleted = store.delete_for_session("session-1")

    assert promotion is not None
    assert promotion.task_id == "promotion-task"
    assert deleted == {"tasks": 1, "attachment_promotions": 1}
    assert state["tasks"] == {}
    assert state["attachment_promotions"] == {}
    assert any(
        sql.startswith("delete from tasks where session_id")
        for sql, _params in state["sql"]
    )


def test_postgres_artifact_store_roundtrip_with_fake_connection():
    state = {
        "sql": [],
        "app_config": {},
        "tasks": {},
        "artifacts": {},
    }
    store = PostgresArtifactStore(
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )
    artifact = ArtifactRecord(
        artifact_id="artifact-1",
        session_id="session-1",
        artifact_type="report",
        title="Report",
        status="ready",
        linked_resource_type="task",
        linked_resource_id="task-1",
        content={"markdown": "# Report"},
        created_at=1.0,
    )

    saved = store.save(artifact)
    loaded = store.get("artifact-1")
    by_session = store.list_by_session("session-1")
    by_linked = store.list_by_linked_resource("task", "task-1")
    deleted = store.delete_by_session("session-1")

    assert saved.artifact_id == "artifact-1"
    assert loaded.content == {"markdown": "# Report"}
    assert [item.artifact_id for item in by_session] == ["artifact-1"]
    assert [item.artifact_id for item in by_linked] == ["artifact-1"]
    assert deleted == 1


def _deck(deck_id: str = "deck-1") -> deck_service.DeckSpec:
    return deck_service.DeckSpec(
        deck_id=deck_id,
        meta=deck_service.DeckMeta(
            title="Board Update",
            subtitle="",
            theme="default",
            created_at="2026-04-25T10:00:00+0800",
            session_id="session-1",
            source_mode="chat_only",
            generator_panel_id="panel-main",
            author="tester",
            audience="ops",
            purpose="validation",
        ),
        generation=deck_service.DeckGeneration(
            source="chat_only",
            target_slide_count=1,
            actual_slide_count=1,
        ),
        slides=[
            deck_service.DeckSlide(
                id="cover",
                type="cover",
                title="Board Update",
                subtitle="",
                layout="hero-title",
                blocks=[],
            )
        ],
        source_registry=[],
    )


def test_postgres_deck_store_roundtrip_with_fake_connection():
    state = {"sql": [], "app_config": {}, "tasks": {}, "decks": {}}
    store = PostgresDeckStore(
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )
    deck = _deck()

    store.save(deck)
    loaded = store.get("deck-1")
    recent = store.list_recent(limit=5)
    session_ids = store.list_ids_by_session("session-1")
    deleted = store.delete_by_session("session-1")

    assert loaded.deck_id == "deck-1"
    assert [item.deck_id for item in recent] == ["deck-1"]
    assert session_ids == ["deck-1"]
    assert deleted == 1


def test_postgres_resource_access_store_roundtrip_with_fake_connection():
    state = {"sql": [], "app_config": {}, "tasks": {}, "resource_grants": {}}
    store = PostgresResourceAccessStore(
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )

    saved = store.upsert_grant(
        resource_type="session",
        resource_id="session-1",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    loaded = store.get_grant(
        resource_type="session",
        resource_id="session-1",
        user_id="viewer",
    )
    listed = store.list_grants(resource_type="session", role="owner")
    total = store.count_grants(role="owner")
    deleted = store.delete_grant(
        resource_type="session",
        resource_id="session-1",
        user_id="viewer",
    )

    assert saved.role == "owner"
    assert loaded is not None
    assert loaded.user_id == "viewer"
    assert [grant.resource_id for grant in listed] == ["session-1"]
    assert total == 1
    assert deleted is True


def test_postgres_identity_store_roundtrip_with_fake_connection():
    state = {
        "sql": [],
        "organizations": {},
        "users": {},
        "memberships": {},
    }
    store = PostgresIdentityStore(
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )

    org = store.upsert_org(org_id="org-1", name="Team", now=1.0)
    user = store.upsert_user(
        user_id="user-1",
        display_name="Ada",
        email="ada@example.test",
        now=2.0,
    )
    membership = store.set_membership(
        org_id="org-1",
        user_id="user-1",
        role="admin",
        now=3.0,
    )

    assert org.name == "Team"
    assert user.email == "ada@example.test"
    assert membership.role == "admin"
    assert [item.org_id for item in store.list_orgs()] == ["org-1"]
    assert [item.user_id for item in store.list_users()] == ["user-1"]
    assert [item.user_id for item in store.list_memberships(org_id="org-1")] == ["user-1"]


def test_postgres_share_link_store_roundtrip_with_fake_connection():
    state = {"sql": [], "share_links": {}}
    store = PostgresShareLinkStore(
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )

    saved = store.upsert(
        share_token="token-1",
        resource_type="session",
        resource_id="session-1",
        expires_at=999.0,
        created_by_ip="127.0.0.1",
    )
    store.record_access("token-1", accessed_ip="127.0.0.2")
    loaded = store.get_active("token-1", now=100.0)
    listed = store.list_links(resource_type="session")
    revoked = store.revoke("token-1")

    assert saved.share_token == "token-1"
    assert loaded is not None
    assert loaded.access_count == 1
    assert [item.resource_id for item in listed] == ["session-1"]
    assert revoked is True
    assert store.get_active("token-1", now=100.0) is None
    assert store.delete_for_resource("session", "session-1") == 1


def test_postgres_sso_session_store_roundtrip_with_fake_connection():
    state = {"sql": [], "sso_sessions": {}}
    store = PostgresSsoSessionStore(
        dsn="postgresql://example/db",
        connection_factory=fake_connection_factory(state),
    )

    saved = store.save(
        token_hash="hash-1",
        user_id="user-1",
        role="admin",
        auth_source="sso_oidc",
        created_at=1.0,
        expires_at=10.0,
    )
    active = store.get_active("hash-1", now=5.0)
    expired = store.get_active("hash-1", now=11.0)

    assert saved.user_id == "user-1"
    assert active is not None
    assert expired is None
    assert state["sso_sessions"] == {}


def test_create_vector_store_adapter_selects_faiss_and_qdrant(monkeypatch):
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "faiss")
    assert isinstance(create_vector_store_adapter(path="kb"), FaissVectorStoreAdapter)

    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("QDRANT_COLLECTION", "kb")
    adapter = create_vector_store_adapter(path="ignored")
    assert isinstance(adapter, QdrantVectorStoreAdapter)
    assert adapter.url == "http://qdrant:6333"
    assert adapter.collection_name == "kb"


def test_faiss_validation_summary_reports_path_and_operations(tmp_path):
    store_path = tmp_path / "faiss-store"
    store_path.mkdir()
    (store_path / "index.faiss").write_bytes(b"faiss")
    (store_path / "index.pkl").write_bytes(b"pickle")
    adapter = FaissVectorStoreAdapter(path=str(store_path))

    summary = adapter.validation_summary()

    assert summary["provider"] == "faiss"
    assert summary["target"]["path"] == str(store_path)
    assert summary["availability"]["available"] is True
    assert summary["availability"]["index_files"] == {
        "index.faiss": True,
        "index.pkl": True,
    }
    assert summary["operations"] == {
        "delete_supported": True,
        "clear_supported": True,
    }
    assert "faiss_load_uses_dangerous_deserialization" in summary["risks"]


def test_faiss_validation_summary_reports_missing_index(tmp_path):
    missing_store = tmp_path / "missing-faiss-store"

    summary = storage_runtime.vector_store_runtime_summary(
        provider="faiss",
        path=str(missing_store),
    )

    assert summary["availability"]["available"] is False
    assert summary["availability"]["status"] == "path_missing"
    assert "faiss_path_missing" in summary["warnings"]


def test_qdrant_validation_summary_is_config_only_without_client():
    def fail_if_called(**kwargs):
        raise AssertionError("validation_summary must not create a Qdrant client")

    adapter = QdrantVectorStoreAdapter(
        collection_name="kb",
        url="http://qdrant:6333",
        api_key="",
        client_factory=fail_if_called,
    )

    summary = adapter.validation_summary()

    assert summary["provider"] == "qdrant"
    assert summary["target"] == {
        "url": "http://qdrant:6333",
        "collection_name": "kb",
        "api_key_configured": False,
    }
    assert summary["availability"]["available"] is True
    assert summary["availability"]["connectivity_checked"] is False
    assert summary["operations"] == {
        "delete_supported": True,
        "clear_supported": True,
    }
    assert "qdrant_collection_not_verified" in summary["warnings"]
    assert "qdrant_delete_removes_collection" in summary["risks"]


def test_storage_runtime_payload_includes_database_and_vector_summaries(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "chat.db"))

    payload = storage_runtime.storage_runtime_payload(
        vector_store_path=str(tmp_path / "vector-store"),
        vector_provider="faiss",
    )

    assert payload["database"]["provider"] == "sqlite"
    assert payload["database"]["availability"]["status"] == "file_missing"
    assert payload["vector_store"]["provider"] == "faiss"
    assert payload["vector_store"]["availability"]["status"] == "path_missing"


def test_storage_runtime_exposes_readiness_and_rollback_contracts(monkeypatch):
    monkeypatch.setenv("STORAGE_INTEGRATION_TEST", "1")
    monkeypatch.setenv("STORAGE_MIGRATION_EXECUTE", "1")
    monkeypatch.delenv("STORAGE_MIGRATION_ROLLBACK", raising=False)

    readiness = storage_runtime.storage_readiness_contract()
    rollback = storage_runtime.storage_rollback_contract()

    assert readiness["gates"]["STORAGE_INTEGRATION_TEST"] is True
    assert readiness["gates"]["STORAGE_MIGRATION_EXECUTE"] is True
    assert readiness["commands"]["execute_migration"] == [
        "python",
        "deploy/validate_storage_migration.py",
        "--execute",
        "--json",
    ]
    assert rollback["gates"]["STORAGE_MIGRATION_ROLLBACK"] is False
    assert "--rollback" in rollback["commands"]["execute_rollback"]


def test_validate_postgres_config_is_offline_and_redacts_secret():
    summary = storage_runtime.validate_postgres_config(
        "postgresql://app_user:secret@postgres:5432/insightdesk"
    )

    assert summary["configured"] is True
    assert summary["valid"] is True
    assert summary["target"] == {
        "dsn_configured": True,
        "dsn_preview": "postgresql://***:***@postgres:5432/insightdesk",
        "scheme": "postgresql",
    }
    assert summary["availability"] == {
        "available": True,
        "status": "configured_not_connected",
        "connectivity_checked": False,
    }
    assert summary["warnings"] == ()


def test_validate_postgres_config_rejects_invalid_scheme():
    summary = storage_runtime.validate_postgres_config("sqlite:///chat.db")

    assert summary["configured"] is True
    assert summary["valid"] is False
    assert summary["target"]["scheme"] == "sqlite"
    assert summary["availability"]["status"] == "invalid_config"
    assert "postgres_dsn_invalid_scheme" in summary["warnings"]


def test_validate_qdrant_config_is_offline_and_checks_url_shape():
    summary = storage_runtime.validate_qdrant_config(
        url="http://qdrant:6333",
        collection_name="kb",
        api_key="secret",
    )

    assert summary["configured"] is True
    assert summary["valid"] is True
    assert summary["target"] == {
        "url": "http://qdrant:6333",
        "collection_name": "kb",
        "api_key_configured": True,
    }
    assert summary["availability"] == {
        "available": True,
        "status": "configured_not_connected",
        "collection_configured": True,
        "connectivity_checked": False,
    }
    assert summary["warnings"] == ()


def test_qdrant_runtime_summary_reports_invalid_url_without_client():
    summary = storage_runtime.vector_store_runtime_summary(
        provider="qdrant",
        url="qdrant:6333",
        collection_name="kb",
    )

    assert summary["configured"] is True
    assert summary["availability"]["available"] is False
    assert summary["availability"]["status"] == "invalid_config"
    assert "qdrant_url_invalid_scheme" in summary["warnings"]
    assert "qdrant_collection_not_verified" not in summary["warnings"]


class FakeQdrantDeleteClient:
    def __init__(self, result=True, should_raise=False):
        self.result = result
        self.should_raise = should_raise
        self.deleted_collections: list[str] = []

    def delete_collection(self, *, collection_name):
        self.deleted_collections.append(collection_name)
        if self.should_raise:
            raise RuntimeError("delete failed")
        return self.result


def test_qdrant_vector_store_adapter_delete_collection_with_fake_client():
    fake_client = FakeQdrantDeleteClient(result=True)
    client_kwargs = []

    def client_factory(**kwargs):
        client_kwargs.append(kwargs)
        return fake_client

    adapter = QdrantVectorStoreAdapter(
        collection_name="kb",
        url="http://qdrant:6333",
        api_key="secret",
        client_factory=client_factory,
    )

    assert adapter.delete() is True
    assert fake_client.deleted_collections == ["kb"]
    assert client_kwargs == [{"url": "http://qdrant:6333", "api_key": "secret"}]


@pytest.mark.parametrize(
    ("client_result", "should_raise", "expected"),
    [
        (False, False, False),
        (True, True, False),
    ],
)
def test_qdrant_vector_store_adapter_delete_failure_semantics(
    client_result,
    should_raise,
    expected,
):
    fake_client = FakeQdrantDeleteClient(
        result=client_result,
        should_raise=should_raise,
    )
    adapter = QdrantVectorStoreAdapter(
        collection_name="kb",
        client_factory=lambda **kwargs: fake_client,
    )

    assert adapter.delete() is expected
    assert fake_client.deleted_collections == ["kb"]


def test_doc_pipeline_loads_remote_vector_store_without_local_path(monkeypatch, tmp_path):
    class FakeRemoteVectorStore:
        pass

    class FakeQdrantAdapter:
        provider = "qdrant"

        def __init__(self):
            self.load_calls: list[str | None] = []

        def from_documents(self, documents, embeddings):
            return FakeRemoteVectorStore()

        def load(self, *, embeddings, path=None):
            self.load_calls.append(path)
            return FakeRemoteVectorStore()

        def save(self, vectorstore, *, path=None):
            return None

    adapter = FakeQdrantAdapter()
    missing_path = tmp_path / "missing-local-vector-store"
    monkeypatch.setattr(doc_pipeline, "create_vector_store_adapter", lambda path: adapter)
    monkeypatch.setattr(DocPipeline, "embeddings", property(lambda self: "fake-embeddings"))

    pipeline = DocPipeline(vector_store_path=str(missing_path))

    assert pipeline.load_store() is True
    assert adapter.load_calls == [str(missing_path)]
    stats = pipeline.get_stats()
    assert stats["vector_store_provider"] == "qdrant"
    assert stats["storage_validation"]["provider"] == "qdrant"
    assert stats["storage_validation"]["availability"]["connectivity_checked"] is False


@pytest.mark.parametrize("delete_result", [True, False])
def test_doc_pipeline_delete_store_calls_remote_adapter_delete(
    monkeypatch,
    tmp_path,
    delete_result,
):
    class FakeQdrantAdapter:
        provider = "qdrant"

        def __init__(self):
            self.delete_calls: list[str | None] = []

        def from_documents(self, documents, embeddings):
            return None

        def load(self, *, embeddings, path=None):
            return None

        def save(self, vectorstore, *, path=None):
            return None

        def delete(self, *, path=None):
            self.delete_calls.append(path)
            return delete_result

    adapter = FakeQdrantAdapter()
    remote_path = tmp_path / "remote-vector-store-placeholder"
    monkeypatch.setattr(doc_pipeline, "create_vector_store_adapter", lambda path: adapter)

    pipeline = DocPipeline(vector_store_path=str(remote_path))
    pipeline.vectorstore = object()

    assert pipeline.delete_store() is delete_result
    assert adapter.delete_calls == [str(remote_path)]
    assert pipeline.vectorstore is None
