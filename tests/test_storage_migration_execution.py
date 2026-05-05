from __future__ import annotations

import argparse
import json
import sqlite3

from deploy.validate_storage_migration import (
    APP_METADATA_TABLES,
    POSTGRES_ADAPTER_TABLES,
    build_migration_report,
    emit_evidence_report,
)


def _args(**overrides):
    defaults = {
        "json": True,
        "sqlite_db_path": "",
        "vector_store_path": "",
        "vector_provider": "qdrant",
        "postgres_dsn": "postgresql://app:secret@db.example:5432/app",
        "qdrant_url": "http://qdrant.example:6333",
        "qdrant_collection": "insightdesk_test_kb",
        "qdrant_api_key": "",
        "qdrant_vector_size": 4,
        "require_postgres_target": False,
        "require_qdrant_target": False,
        "fail_on_warnings": False,
        "execute": False,
        "rollback_plan": False,
        "rollback": False,
        "confirm_drop_postgres_adapter_tables": False,
        "confirm_delete_qdrant_collection": False,
        "allow_prod_qdrant_rollback": False,
        "report_path": "",
        "archive_dir": "",
        "history_path": "",
        "manifest_path": "",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _sqlite_source(tmp_path):
    db_path = tmp_path / "source.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                params_json TEXT NOT NULL,
                session_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                result TEXT,
                error TEXT,
                progress INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE attachment_promotions (
                attachment_id TEXT NOT NULL,
                vector_store_path TEXT NOT NULL,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                attachment_name TEXT,
                session_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                result TEXT,
                error TEXT,
                PRIMARY KEY (attachment_id, vector_store_path)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                title TEXT DEFAULT '',
                is_archived INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0,
                is_pinned INTEGER DEFAULT 0,
                session_order REAL DEFAULT 0,
                tags_json TEXT DEFAULT '[]',
                workspace_id TEXT DEFAULT 'workspace-default'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                color TEXT DEFAULT 'blue',
                default_panels_json TEXT DEFAULT '[]',
                tool_config_json TEXT DEFAULT '{}',
                output_preset_json TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE organizations (
                org_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                email TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE memberships (
                org_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (org_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE share_links (
                share_token TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked_at REAL,
                created_by_ip TEXT DEFAULT '',
                created_user_agent TEXT DEFAULT '',
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at REAL,
                last_accessed_ip TEXT DEFAULT '',
                last_accessed_user_agent TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE sso_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                auth_source TEXT NOT NULL DEFAULT 'sso_oidc',
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO app_config VALUES ('theme', 'dark', 1.0)")
        conn.execute(
            """
            INSERT INTO tasks VALUES (
                'task-1', 'demo', 'completed', '{}', 'session-1',
                1.0, 2.0, 'ok', NULL, 100
            )
            """
        )
        conn.execute(
            """
            INSERT INTO workspaces VALUES (
                'workspace-default', 'Default', '', 'blue', '[]', '{}', '{}', 1, 1.0, 2.0
            )
            """
        )
        conn.execute(
            """
            INSERT INTO sessions VALUES (
                'session-1', 1.0, 2.0, 'Session', 0, 0, 0, 0.0, '[]', 'workspace-default'
            )
            """
        )
        conn.execute("INSERT INTO organizations VALUES ('org-1', 'Team', '', 1.0, 2.0)")
        conn.execute(
            "INSERT INTO users VALUES ('user-1', 'Ada', 'ada@example.test', 1.0, 2.0)"
        )
        conn.execute("INSERT INTO memberships VALUES ('org-1', 'user-1', 'admin', 1.0, 2.0)")
        conn.execute(
            """
            INSERT INTO share_links VALUES (
                'token-1', 'session', 'session-1', 1.0, 999.0, NULL, '', '', 0, NULL, '', ''
            )
            """
        )
        conn.execute(
            "INSERT INTO sso_sessions VALUES ('hash-1', 'user-1', 'admin', 'sso_oidc', 1.0, 999.0)"
        )
    return db_path


def test_storage_migration_execute_requires_env_gate(tmp_path, monkeypatch):
    db_path = _sqlite_source(tmp_path)
    monkeypatch.delenv("STORAGE_MIGRATION_EXECUTE", raising=False)

    report = build_migration_report(
        _args(sqlite_db_path=str(db_path), execute=True),
        postgres_executor=lambda *_args: {"errors": [], "warnings": []},
        qdrant_executor=lambda *_args: {"errors": [], "warnings": []},
    )

    assert report["ok"] is False
    assert report["actions"]["executed"] is False
    assert report["closure"]["status"] == "blocked"
    assert report["actions"]["real_environment_gate"]["execute"]["status"] == "blocked"
    assert any(
        check["name"] == "execute_env_gate" and check["status"] == "blocked"
        for check in report["checks"]["pre"]
    )
    assert all(check["status"] == "skipped" for check in report["checks"]["post"][:2])
    assert "missing_env:STORAGE_MIGRATION_EXECUTE" in report["errors"]


def test_storage_migration_execute_uses_injected_real_executors(tmp_path, monkeypatch):
    db_path = _sqlite_source(tmp_path)
    monkeypatch.setenv("STORAGE_MIGRATION_EXECUTE", "1")
    calls = {"postgres": [], "qdrant": []}

    def fake_postgres(dsn: str, sqlite_db_path: str) -> dict:
        calls["postgres"].append((dsn, sqlite_db_path))
        return {
            "checked": True,
            "copied_rows": {"app_config": 1, "tasks": 1, "attachment_promotions": 0},
            "errors": [],
            "warnings": [],
        }

    def fake_qdrant(url: str, api_key: str, collection: str, vector_size: int) -> dict:
        calls["qdrant"].append((url, api_key, collection, vector_size))
        return {
            "checked": True,
            "collection": collection,
            "created": True,
            "errors": [],
            "warnings": [],
        }

    report = build_migration_report(
        _args(sqlite_db_path=str(db_path), execute=True),
        postgres_executor=fake_postgres,
        qdrant_executor=fake_qdrant,
    )

    assert report["ok"] is True
    assert report["actions"]["executed"] is True
    assert report["closure"]["status"] == "executed"
    assert report["closure"]["migration_ready"] is True
    assert report["closure"]["postgres_checked"] is True
    assert report["closure"]["qdrant_checked"] is True
    assert report["evidence_bundle"]["status"] == "executed"
    assert any(
        check["name"] == "postgres_execute_action" and check["status"] == "passed"
        for check in report["checks"]["post"]
    )
    assert any(
        check["name"] == "qdrant_execute_action" and check["status"] == "passed"
        for check in report["checks"]["post"]
    )
    assert report["actions"]["postgres"]["copied_rows"]["tasks"] == 1
    assert calls["postgres"] == [
        ("postgresql://app:secret@db.example:5432/app", str(db_path))
    ]
    assert calls["qdrant"] == [
        ("http://qdrant.example:6333", "", "insightdesk_test_kb", 4)
    ]


def test_storage_migration_postgres_coverage_includes_content_and_acl_tables(tmp_path):
    db_path = _sqlite_source(tmp_path)

    report = build_migration_report(_args(sqlite_db_path=str(db_path)))

    assert set(report["coverage"]["postgres_adapter_tables"]) >= {
        "artifacts",
        "bookmarks",
        "decks",
        "memberships",
        "organizations",
        "resource_grants",
        "retrieval_feedback",
        "sessions",
        "session_memory",
        "session_panels",
        "share_links",
        "sso_sessions",
        "system_prompts",
        "users",
        "workspaces",
    }
    assert "artifacts" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "decks" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "resource_grants" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "organizations" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "users" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "memberships" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "sessions" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "messages" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "message_search" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "security_audit_events" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "session_memory" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "session_panels" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert "retrieval_feedback" not in report["coverage"]["pending_postgres_adapter_tables"]
    assert len(report["coverage"]["pending_postgres_adapter_tables"]) == 0
    assert len(report["coverage"]["pending_postgres_adapter_tables"]) == (
        len(APP_METADATA_TABLES) - len(POSTGRES_ADAPTER_TABLES)
    )


def test_storage_migration_report_includes_qdrant_backfill_plan(tmp_path):
    db_path = _sqlite_source(tmp_path)

    report = build_migration_report(_args(sqlite_db_path=str(db_path)))

    plan = report["qdrant_backfill_plan"]
    assert plan["dry_run_default"] is True
    assert plan["destructive"] is False
    assert plan["execute_env"] == "QDRANT_BACKFILL_EXECUTE"
    assert "deploy/run_qdrant_backfill.py" in plan["command"]
    assert "--allow-dangerous-faiss-deserialization" in plan["command"]


def test_storage_migration_rollback_contract_requires_confirmation(monkeypatch):
    monkeypatch.setenv("STORAGE_MIGRATION_ROLLBACK", "1")

    report = build_migration_report(_args(rollback=True))

    assert report["ok"] is False
    assert report["actions"]["mode"] == "rollback"
    assert report["closure"]["status"] == "blocked"
    assert report["closure"]["rollback_ready"] is False
    assert report["closure"]["blockers"] == report["errors"]
    assert "rollback_requires_confirm_drop_postgres_adapter_tables" in report["errors"]
    assert report["rollback_plan"]["postgres"]["destructive"] is True
    assert report["rollback_plan"]["requires"]["env"] == "STORAGE_MIGRATION_ROLLBACK"
    assert (
        report["rollback_plan"]["postgres"]["requires"]["confirmation_flag"]
        == "--confirm-drop-postgres-adapter-tables"
    )
    assert report["rollback_plan"]["evidence"]["required"] is True


def test_storage_migration_rollback_uses_injected_executors(monkeypatch):
    monkeypatch.setenv("STORAGE_MIGRATION_ROLLBACK", "1")
    calls = {"postgres": [], "qdrant": []}

    report = build_migration_report(
        _args(
            rollback=True,
            confirm_drop_postgres_adapter_tables=True,
            confirm_delete_qdrant_collection=True,
        ),
        postgres_rollback_executor=lambda dsn: calls["postgres"].append(dsn)
        or {"checked": True, "dropped_tables": ["attachment_promotions"], "errors": [], "warnings": []},
        qdrant_rollback_executor=lambda url, api_key, collection: calls["qdrant"].append(
            (url, api_key, collection)
        )
        or {"checked": True, "deleted": True, "errors": [], "warnings": []},
    )

    assert report["ok"] is True
    assert report["actions"]["executed"] is True
    assert report["closure"]["status"] == "executed"
    assert report["closure"]["rollback_ready"] is True
    assert report["closure"]["postgres_checked"] is True
    assert report["closure"]["qdrant_checked"] is True
    assert report["actions"]["real_environment_gate"]["rollback"]["status"] == "passed"
    assert report["evidence_bundle"]["status"] == "executed"
    assert any(
        check["name"] == "postgres_rollback_action" and check["status"] == "passed"
        for check in report["checks"]["post"]
    )
    assert any(
        check["name"] == "qdrant_rollback_action" and check["status"] == "passed"
        for check in report["checks"]["post"]
    )
    assert calls["postgres"] == ["postgresql://app:secret@db.example:5432/app"]
    assert calls["qdrant"] == [("http://qdrant.example:6333", "", "insightdesk_test_kb")]


def test_storage_migration_rollback_rejects_invalid_qdrant_target(monkeypatch):
    monkeypatch.setenv("STORAGE_MIGRATION_ROLLBACK", "1")
    monkeypatch.delenv("QDRANT_URL", raising=False)
    calls = {"qdrant": 0}

    report = build_migration_report(
        _args(
            rollback=True,
            qdrant_url="ftp://qdrant.example:6333",
            confirm_drop_postgres_adapter_tables=True,
            confirm_delete_qdrant_collection=True,
            allow_prod_qdrant_rollback=True,
        ),
        postgres_rollback_executor=lambda _dsn: {
            "checked": True,
            "dropped_tables": [],
            "errors": [],
            "warnings": [],
        },
        qdrant_rollback_executor=lambda *_args: calls.__setitem__("qdrant", 1) or {},
    )

    assert report["ok"] is False
    assert report["actions"]["executed"] is False
    assert "qdrant_target_invalid" in report["errors"]
    assert report["closure"]["status"] == "blocked"
    assert calls["qdrant"] == 0


def test_storage_migration_report_writes_evidence_without_execution(tmp_path):
    report_path = tmp_path / "storage-migration-preflight.json"
    archive_dir = tmp_path / "archive"
    history_path = tmp_path / "history.json"
    manifest_path = tmp_path / "manifest.json"
    report = build_migration_report(
        _args(
            sqlite_db_path=str(tmp_path / "missing.db"),
            report_path=str(report_path),
            archive_dir=str(archive_dir),
            history_path=str(history_path),
            manifest_path=str(manifest_path),
        )
    )

    emit_evidence_report(
        report,
        report_path=str(report_path),
        archive_dir=str(archive_dir),
        history_path=str(history_path),
        manifest_path=str(manifest_path),
    )

    written = json.loads(report_path.read_text(encoding="utf-8"))
    history = json.loads(history_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert report["actions"]["executed"] is False
    assert report["closure"]["evidence_ready"] is True
    assert report["closure"]["evidence_targets"]["report_path"] == str(report_path)
    assert report["closure"]["evidence_targets"]["manifest_path"] == str(manifest_path)
    assert written["contracts"]["evidence"]["report_path"] == str(report_path)
    assert written["contracts"]["evidence"]["manifest_path"] == str(manifest_path)
    assert written["evidence"]["id"] == "storage_migration_preflight"
    assert written["evidence"]["status"] == report["closure"]["status"]
    assert written["evidence"]["manifest_path"] == str(manifest_path)
    assert written["evidence_bundle"]["id"] == "storage_migration_preflight"
    assert written["evidence_bundle"]["targets"]["manifest_path"] == str(manifest_path)
    assert written["evidence_bundle"]["artifacts"]["report"]["written"] is True
    assert written["evidence_bundle"]["artifacts"]["history"]["written"] is True
    assert written["evidence_bundle"]["artifacts"]["manifest"]["written"] is True
    assert written["evidence"]["archive_path"]
    assert archive_dir.is_dir()
    assert history[-1]["mode"] == "preflight"
    assert history[-1]["status"] == report["closure"]["status"]
    assert history[-1]["evidence_bundle_id"] == "storage_migration_preflight"
    assert history[-1]["report_path"] == str(report_path)
    assert history[-1]["manifest_path"] == str(manifest_path)
    manifest_entry = manifest["reports"]["storage_migration_preflight"]
    assert manifest["schema_version"] == "1"
    assert manifest["updated_at"]
    assert manifest_entry["id"] == "storage_migration_preflight"
    assert manifest_entry["status"] == report["closure"]["status"]
    assert manifest_entry["ok"] == report["ok"]
    assert manifest_entry["report_path"] == str(report_path)
    assert manifest_entry["archive_path"] == written["evidence"]["archive_path"]
    assert manifest_entry["history_path"] == str(history_path)
    assert manifest_entry["manifest_path"] == str(manifest_path)
    assert manifest_entry["blockers"] == report["closure"]["blockers"]
    assert manifest_entry["finished_at"]
