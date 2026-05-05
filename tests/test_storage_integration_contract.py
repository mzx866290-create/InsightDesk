from __future__ import annotations

import json

from deploy.run_storage_integration_check import build_integration_report, emit_evidence_report


def test_storage_integration_check_skips_by_default() -> None:
    report = build_integration_report({})

    assert report["ok"] is True
    assert report["status"] == "skipped"
    assert report["integration_enabled"] is False
    assert report["gate"]["status"] == "skipped"
    assert report["checked"] == []
    assert report["skipped"] == [
        {"name": "postgres", "reason": "integration_disabled"},
        {"name": "qdrant", "reason": "integration_disabled"},
    ]
    assert report["postgres"]["checked"] is False
    assert report["qdrant"]["checked"] is False
    assert report["evidence_bundle"]["status"] == "skipped"
    assert all(check["status"] == "skipped" for check in report["post_checks"][:2])


def test_storage_integration_check_reports_missing_enabled_config() -> None:
    report = build_integration_report({"STORAGE_INTEGRATION_TEST": "1"})

    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert report["checked"] == []
    assert "postgres:postgres_dsn_missing" in report["errors"]
    assert "qdrant:qdrant_url_missing" in report["errors"]
    assert {"name": "postgres", "reason": "invalid_config"} in report["skipped"]
    assert {"name": "qdrant", "reason": "missing_url"} in report["skipped"]
    assert any(
        check["name"] == "postgres_config" and check["status"] == "blocked"
        for check in report["pre_checks"]
    )


def test_storage_integration_check_redacts_json_and_uses_injected_checkers() -> None:
    def fake_postgres_checker(dsn: str) -> dict:
        assert dsn == "postgresql://app_user:super-secret@db.example:5432/app"
        return {
            "connectivity": {"checked": True, "available": True},
            "schema": {
                "required_tables": ["app_config"],
                "present_tables": ["app_config"],
                "missing_tables": [],
                "ready": True,
            },
            "warnings": [],
            "errors": [],
        }

    def fake_qdrant_checker(
        url: str,
        api_key: str,
        collection: str,
        test_collection: str,
    ) -> dict:
        assert url == "https://user:pass@qdrant.example:6333/tenant?token=hidden"
        assert api_key == "qdrant-secret"
        assert collection == "prod_kb"
        assert test_collection == "insightdesk_test_contract"
        return {
            "collections_endpoint": {
                "checked": True,
                "available": True,
                "collection_count": 1,
            },
            "roundtrip": {
                "checked": True,
                "created": True,
                "deleted": True,
                "point_count": 1,
            },
            "warnings": [],
            "errors": [],
        }

    report = build_integration_report(
        {
            "STORAGE_INTEGRATION_TEST": "1",
            "DATABASE_URL": "postgresql://app_user:super-secret@db.example:5432/app",
            "QDRANT_URL": "https://user:pass@qdrant.example:6333/tenant?token=hidden",
            "QDRANT_API_KEY": "qdrant-secret",
            "QDRANT_COLLECTION": "prod_kb",
            "QDRANT_TEST_COLLECTION": "insightdesk_test_contract",
        },
        postgres_checker=fake_postgres_checker,
        qdrant_checker=fake_qdrant_checker,
    )

    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert report["ok"] is True
    assert report["status"] == "passed"
    assert report["checked"] == ["postgres", "qdrant"]
    assert report["gate"]["status"] == "passed"
    assert report["postgres"]["dsn"] == "postgresql://***:***@db.example:5432/app"
    assert report["qdrant"]["url"] == "https://***:***@qdrant.example:6333/tenant"
    assert report["qdrant"]["collection"] == "prod_kb"
    assert report["qdrant"]["test_collection"] == "insightdesk_test_contract"
    assert "super-secret" not in encoded
    assert "qdrant-secret" not in encoded
    assert "token=hidden" not in encoded
    assert any(
        check["name"] == "postgres_real_check" and check["status"] == "passed"
        for check in report["post_checks"]
    )
    assert any(
        check["name"] == "qdrant_real_check" and check["status"] == "passed"
        for check in report["post_checks"]
    )


def test_storage_integration_check_rejects_unsafe_qdrant_test_collection() -> None:
    calls = {"qdrant": 0}

    def fake_qdrant_checker(*args) -> dict:
        calls["qdrant"] += 1
        return {}

    report = build_integration_report(
        {
            "STORAGE_INTEGRATION_TEST": "1",
            "DATABASE_URL": "postgresql://app_user:secret@db.example:5432/app",
            "QDRANT_URL": "http://qdrant.example:6333",
            "QDRANT_COLLECTION": "prod_kb",
            "QDRANT_TEST_COLLECTION": "prod_kb",
        },
        postgres_checker=lambda _dsn: {"warnings": [], "errors": []},
        qdrant_checker=fake_qdrant_checker,
    )

    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert "qdrant:test_collection_prefix_required" in report["errors"]
    assert {"name": "qdrant", "reason": "unsafe_test_collection"} in report["skipped"]
    assert calls["qdrant"] == 0


def test_storage_integration_check_json_schema_contains_safe_targets() -> None:
    report = build_integration_report({})

    assert set(report) >= {
        "ok",
        "integration_enabled",
        "checked",
        "skipped",
        "errors",
        "warnings",
        "postgres",
        "qdrant",
        "status",
        "gate",
        "pre_checks",
        "post_checks",
        "evidence_bundle",
    }
    assert set(report["postgres"]) >= {"dsn", "schema", "warnings", "errors"}
    assert set(report["qdrant"]) >= {
        "url",
        "collection",
        "test_collection",
        "collections_endpoint",
        "warnings",
        "errors",
    }


def test_storage_integration_check_writes_local_evidence(tmp_path) -> None:
    report_path = tmp_path / "storage-real-integration.json"
    archive_dir = tmp_path / "archive"
    history_path = tmp_path / "history.json"
    manifest_path = tmp_path / "manifest.json"
    report = build_integration_report({})

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

    assert written["ok"] is True
    assert written["status"] == "skipped"
    assert written["integration_enabled"] is False
    assert written["evidence"]["report_path"] == str(report_path)
    assert written["evidence"]["history_path"] == str(history_path)
    assert written["evidence"]["manifest_path"] == str(manifest_path)
    assert written["evidence_bundle"]["targets"]["manifest_path"] == str(manifest_path)
    assert written["evidence_bundle"]["artifacts"]["report"]["written"] is True
    assert written["evidence_bundle"]["artifacts"]["history"]["written"] is True
    assert written["evidence_bundle"]["artifacts"]["manifest"]["written"] is True
    assert written["evidence"]["archive_path"]
    assert archive_dir.is_dir()
    assert history[-1]["id"] == "storage_real_integration"
    assert history[-1]["status"] == "skipped"
    assert history[-1]["evidence_bundle_id"] == "storage_real_integration"
    assert history[-1]["report_path"] == str(report_path)
    assert history[-1]["manifest_path"] == str(manifest_path)
    manifest_entry = manifest["reports"]["storage_real_integration"]
    assert manifest["schema_version"] == "1"
    assert manifest["updated_at"]
    assert manifest_entry["id"] == "storage_real_integration"
    assert manifest_entry["status"] == "skipped"
    assert manifest_entry["ok"] is True
    assert manifest_entry["report_path"] == str(report_path)
    assert manifest_entry["archive_path"] == written["evidence"]["archive_path"]
    assert manifest_entry["history_path"] == str(history_path)
    assert manifest_entry["manifest_path"] == str(manifest_path)
    assert manifest_entry["blockers"] == []
    assert manifest_entry["finished_at"]
