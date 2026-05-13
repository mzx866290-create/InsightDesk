import json

from fastapi.testclient import TestClient

import backend.api_server as api_server
from backend.stores.security_audit_store import SQLiteSecurityAuditStore


def _set_remote_admin_catalog(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.delenv("EDITOR_API_TOKEN", raising=False)
    monkeypatch.delenv("VIEWER_API_TOKEN", raising=False)
    monkeypatch.setenv(
        "APP_AUTH_TOKENS_JSON",
        json.dumps(
            [
                {
                    "token": "admin-token",
                    "user_id": "admin.user",
                    "role": "admin",
                    "auth_source": "summary_test",
                },
                {
                    "token": "viewer-token",
                    "user_id": "viewer.user",
                    "role": "viewer",
                    "auth_source": "summary_test",
                },
            ]
        ),
    )


def _patch_security_audit_store(monkeypatch, tmp_path):
    store = SQLiteSecurityAuditStore(db_path=str(tmp_path / "security-audit.db"))
    monkeypatch.setattr(api_server, "_security_audit_store", store)
    # Summary must be backed by the shared persisted audit store, not the memory window.
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    return store


def _append_event(
    store,
    *,
    timestamp: float,
    action: str,
    result: str = "ok",
    details: str = "",
    user_id: str = "seed.user",
    request_id: str | None = None,
    tenant_id: str = "",
    org_id: str = "",
    legal_hold: bool = False,
):
    store.append(
        {
            "timestamp": timestamp,
            "request_id": request_id or f"req-{int(timestamp)}",
            "action": action,
            "result": result,
            "ip": "203.0.113.10",
            "is_local": False,
            "auth_mode": "bearer",
            "auth_source": "summary_seed",
            "user_id": user_id,
            "user_role": "admin",
            "details": details,
            "tenant_id": tenant_id,
            "org_id": org_id,
            "legal_hold": legal_hold,
        }
    )


def test_security_audit_summary_filters_by_category_and_hides_secret_details(
    monkeypatch, tmp_path
):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(
        store,
        timestamp=1,
        action="upsert_resource_grant",
        result="ok",
        details="resource_id=deck-1 token=raw-access-token",
    )
    _append_event(
        store,
        timestamp=2,
        action="resource_access_denied",
        result="rejected",
        details="resource_id=deck-2 secret=raw-client-secret",
    )
    _append_event(
        store,
        timestamp=3,
        action="get_auth_tokens",
        result="ok",
        details="token=raw-auth-token",
    )
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-summary",
        headers={"X-API-Token": "admin-token"},
        params={"category": "access"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "access"
    assert payload["total"] == 2
    assert payload["recent_count"] == 2
    assert payload["action_counts"] == {
        "resource_access_denied": 1,
        "upsert_resource_grant": 1,
    }
    assert payload["result_counts"] == {"ok": 1, "rejected": 1}
    assert "get_auth_tokens" not in payload["action_counts"]

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "raw-access-token" not in rendered_payload
    assert "raw-client-secret" not in rendered_payload
    assert "raw-auth-token" not in rendered_payload


def test_security_audit_summary_aggregates_actions_and_results_from_store(
    monkeypatch, tmp_path
):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(store, timestamp=1, action="get_auth_whoami", result="ok")
    _append_event(store, timestamp=2, action="get_auth_whoami", result="ok")
    _append_event(store, timestamp=3, action="remote_auth_guard", result="rejected")
    _append_event(store, timestamp=4, action="upsert_identity_user", result="blocked")
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-summary",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == ""
    assert payload["total"] == 4
    assert payload["recent_count"] == 4
    assert payload["action_counts"] == {
        "get_auth_whoami": 2,
        "remote_auth_guard": 1,
        "upsert_identity_user": 1,
    }
    assert payload["result_counts"] == {"blocked": 1, "ok": 2, "rejected": 1}


def test_security_audit_siem_export_redacts_json_and_ndjson(monkeypatch, tmp_path):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(
        store,
        timestamp=10,
        request_id="req-siem-1",
        action="upsert_resource_grant",
        result="ok",
        user_id="alice",
        tenant_id="tenant-a",
        org_id="org-a",
        details=(
            "org_id=org-a tenant_id=tenant-a "
            "token=raw-access-token client_secret=raw-client-secret"
        ),
    )
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-siem-export",
        headers={"Authorization": "Bearer admin-token"},
        params={"format": "json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "json"
    assert payload["content_type"] == "application/json"
    assert payload["total"] == 1
    event = payload["events"][0]
    assert event["action"] == "upsert_resource_grant"
    assert event["result"] == "ok"
    assert event["category"] == "access"
    assert event["user_id"] == "alice"
    assert event["tenant"] == "tenant-a"
    assert event["org"] == "org-a"
    assert event["ip"] == "203.0.113.10"
    assert event["request_id"] == "req-siem-1"

    rendered_payload = json.dumps(payload, ensure_ascii=False)
    assert "raw-access-token" not in rendered_payload
    assert "raw-client-secret" not in rendered_payload
    assert "token=<redacted>" in rendered_payload
    assert "client_secret=<redacted>" in rendered_payload

    ndjson_response = client.get(
        "/api/security/audit-siem-export",
        headers={"Authorization": "Bearer admin-token"},
        params={"format": "ndjson", "action": "upsert_resource_grant"},
    )

    assert ndjson_response.status_code == 200
    ndjson_payload = ndjson_response.json()
    assert ndjson_payload["format"] == "ndjson"
    assert ndjson_payload["content_type"] == "application/x-ndjson"
    lines = [line for line in ndjson_payload["content"].splitlines() if line]
    assert len(lines) == 1
    exported = json.loads(lines[0])
    assert exported["request_id"] == "req-siem-1"
    assert "raw-access-token" not in ndjson_payload["content"]


def test_security_audit_aggregate_report_groups_cross_tenant_dimensions(
    monkeypatch, tmp_path
):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(
        store,
        timestamp=20,
        action="upsert_resource_grant",
        user_id="alice",
        tenant_id="tenant-a",
        org_id="org-a",
    )
    _append_event(
        store,
        timestamp=21,
        action="upsert_resource_grant",
        user_id="alice",
        tenant_id="tenant-a",
        org_id="org-a",
    )
    _append_event(
        store,
        timestamp=22,
        action="resource_access_denied",
        result="rejected",
        user_id="bob",
        tenant_id="tenant-b",
        org_id="org-b",
    )
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-aggregate-report",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_by"] == [
        "tenant",
        "org",
        "user_id",
        "category",
        "action",
        "result",
    ]
    assert payload["total"] == 3
    rows = {
        (
            row["tenant"],
            row["org"],
            row["user_id"],
            row["category"],
            row["action"],
            row["result"],
        ): row["count"]
        for row in payload["rows"]
    }
    assert rows[
        ("tenant-a", "org-a", "alice", "access", "upsert_resource_grant", "ok")
    ] == 2
    assert rows[
        (
            "tenant-b",
            "org-b",
            "bob",
            "access",
            "resource_access_denied",
            "rejected",
        )
    ] == 1
    assert payload["totals"]["tenant"] == {"tenant-a": 2, "tenant-b": 1}
    assert payload["totals"]["org"] == {"org-a": 2, "org-b": 1}
    assert payload["totals"]["user_id"] == {"alice": 2, "bob": 1}


def test_security_audit_events_filter_by_category_time_and_user(
    monkeypatch, tmp_path
):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(
        store,
        timestamp=100,
        action="upsert_resource_grant",
        user_id="seed.user",
    )
    _append_event(
        store,
        timestamp=110,
        action="custom_legacy_action",
        user_id="seed.user",
    )
    _append_event(
        store,
        timestamp=120,
        action="resource_access_denied",
        result="rejected",
        user_id="other.user",
    )
    _append_event(
        store,
        timestamp=130,
        action="resource_access_denied",
        result="blocked",
        user_id="seed.user",
    )
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-events",
        headers={"Authorization": "Bearer admin-token"},
        params={
            "category": "access",
            "user_id": "seed.user",
            "since": "125",
            "until": "not-a-number",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["events"][0]["timestamp"] == 130
    assert payload["events"][0]["action"] == "resource_access_denied"
    assert payload["events"][0]["user_id"] == "seed.user"
    assert payload["filters"] == {
        "action": "",
        "result": "",
        "category": "access",
        "user_id": "seed.user",
        "since": 125.0,
        "until": None,
    }

    unknown_response = client.get(
        "/api/security/audit-events",
        headers={"Authorization": "Bearer admin-token"},
        params={"category": "uncategorized"},
    )

    assert unknown_response.status_code == 200
    unknown_payload = unknown_response.json()
    assert unknown_payload["total"] == 1
    assert unknown_payload["events"][0]["action"] == "custom_legacy_action"


def test_security_audit_cleanup_dry_run_does_not_delete_events(
    monkeypatch, tmp_path
):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(store, timestamp=100, action="get_auth_whoami")
    _append_event(store, timestamp=110, action="get_auth_tokens")
    _append_event(store, timestamp=120, action="get_security_status")
    client = TestClient(api_server.app)

    response = client.post(
        "/api/security/audit-events/cleanup",
        headers={"Authorization": "Bearer admin-token"},
        params={"keep_latest": "1", "dry_run": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["keep_latest"] == 1
    assert payload["would_delete_count"] == 2
    assert payload["deleted_count"] == 0
    assert payload["memory_deleted_count"] == 0
    assert payload["includes_cleanup_event"] is True
    assert store.count_events() == 4


def test_security_audit_archive_policy_and_legal_hold_preserve_cleanup(
    monkeypatch, tmp_path
):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(
        store,
        timestamp=1,
        request_id="req-archive-delete",
        action="upsert_resource_grant",
        details="org_id=org-a tenant_id=tenant-a token=raw-token",
    )
    _append_event(
        store,
        timestamp=2,
        request_id="req-archive-hold",
        action="resource_access_denied",
        result="rejected",
        details="org_id=org-a tenant_id=tenant-a secret=raw-secret",
    )
    client = TestClient(api_server.app)

    hold_response = client.post(
        "/api/security/audit-events/legal-hold",
        headers={"Authorization": "Bearer admin-token"},
        params={"request_id": "req-archive-hold", "legal_hold": "true"},
    )

    assert hold_response.status_code == 200
    assert hold_response.json() == {
        "request_id": "req-archive-hold",
        "legal_hold": True,
        "updated_count": 1,
    }

    preview_response = client.get(
        "/api/security/audit-archive-policy",
        headers={"Authorization": "Bearer admin-token"},
        params={"retention_days": "1"},
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["mode"] == "preview"
    assert preview["history_limit"] >= 1
    assert preview["cutoff_timestamp"] is not None
    assert preview["archive_candidate_count"] == 1
    assert preview["legal_hold_count"] == 1
    assert preview["legal_hold_preserved_count"] == 1
    assert preview["cleanup_behavior"]["cleanup_preserves_legal_hold"] is True
    assert preview["events"] == []

    export_response = client.get(
        "/api/security/audit-archive-policy",
        headers={"Authorization": "Bearer admin-token"},
        params={"mode": "export", "retention_days": "1"},
    )

    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["export_count"] == 1
    assert export_payload["history_limit"] >= 1
    assert export_payload["cutoff_timestamp"] is not None
    assert export_payload["events"][0]["request_id"] == "req-archive-delete"
    rendered_export = json.dumps(export_payload, ensure_ascii=False)
    assert "raw-token" not in rendered_export
    assert "raw-secret" not in rendered_export

    cleanup_response = client.post(
        "/api/security/audit-events/cleanup",
        headers={"Authorization": "Bearer admin-token"},
        params={"keep_latest": "0"},
    )

    assert cleanup_response.status_code == 200
    remaining_events = store.list_events(limit=10)
    remaining_by_request_id = {event.request_id: event for event in remaining_events}
    assert "req-archive-delete" not in remaining_by_request_id
    assert remaining_by_request_id["req-archive-hold"].legal_hold is True


def test_security_audit_summary_categorizes_task_approval_actions(
    monkeypatch, tmp_path
):
    _set_remote_admin_catalog(monkeypatch)
    store = _patch_security_audit_store(monkeypatch, tmp_path)
    _append_event(store, timestamp=1, action="task_approval_decision", result="ok")
    _append_event(
        store,
        timestamp=2,
        action="task_approval_batch_decision",
        result="ok",
    )
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-summary",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["unknown_action_count"] == 0
    assert payload["category_counts"]["audit"] == 2
    assert payload["action_counts"] == {
        "task_approval_batch_decision": 1,
        "task_approval_decision": 1,
    }


def test_security_audit_action_catalog_includes_task_approval_policy_update(
    monkeypatch,
):
    _set_remote_admin_catalog(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-actions",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    actions = {item["action"]: item for item in response.json()["actions"]}
    assert actions["task_approval_policy_update"] == {
        "action": "task_approval_policy_update",
        "category": "audit",
        "minimum_reader_role": "admin",
        "description": "An admin updated the runtime policy for task approval gates.",
    }
