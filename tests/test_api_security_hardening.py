import logging

from fastapi.testclient import TestClient

import api_server
from api_share_helpers import encode_share_token
import chat_store


def test_security_headers_are_attached_to_responses():
    client = TestClient(api_server.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert (
        response.headers["Permissions-Policy"]
        == "camera=(), microphone=(), geolocation=()"
    )


def test_remote_admin_routes_require_admin_token(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    client = TestClient(api_server.app)

    denied = client.post("/api/agents/reset")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "缺少有效的管理令牌"

    allowed = client.post(
        "/api/agents/reset",
        headers={"X-Admin-Token": "demo-admin-token"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True


def test_remote_share_routes_require_strong_share_secret(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setattr(api_server, "SHARE_LINK_SECRET", "local-share-secret")
    history = chat_store.SQLiteChatMessageHistory("session-remote-share")
    history.add_user_message("share this")
    client = TestClient(api_server.app)

    response = client.post("/api/sessions/session-remote-share/share")

    assert response.status_code == 503
    assert response.json()["detail"] == "远程分享已禁用，请配置强 SHARE_LINK_SECRET 后再启用"


def test_remote_document_upload_requires_admin_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    client = TestClient(api_server.app)

    denied = client.post(
        "/api/documents/upload",
        files=[("files", ("demo.txt", b"hello world", "text/plain"))],
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "缺少有效的管理令牌"

    allowed = client.post(
        "/api/documents/upload",
        headers={"X-Admin-Token": "demo-admin-token"},
        files=[("files", ("demo.txt", b"hello world", "text/plain"))],
    )
    assert allowed.status_code != 403


def test_remote_read_sensitive_routes_require_admin_token(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    client = TestClient(api_server.app)

    cases = [
        ("get", "/api/config", {}),
        ("get", "/api/prompts", {}),
        ("get", "/api/documents/stats", {}),
        ("get", "/api/knowledge-bases", {}),
        ("get", "/api/knowledge-base/health", {}),
        ("get", "/api/knowledge-base/chunks", {}),
        ("post", "/api/knowledge-base/test-retrieval", {"json": {"query": "alpha"}}),
    ]

    for method, url, kwargs in cases:
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == 403, url
        assert response.json()["detail"] == "缺少有效的管理令牌"


def test_security_audit_logs_include_auth_and_identity_metadata(
    monkeypatch, caplog
):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    client = TestClient(api_server.app)

    with caplog.at_level(logging.INFO, logger=api_server.logger.name):
        response = client.get(
            "/api/config",
            headers={
                "X-Admin-Token": "demo-admin-token",
                "X-User-Id": "alice\nops",
                "X-User-Role": "platform\tadmin",
            },
        )

    assert response.status_code == 200
    messages = "\n".join(caplog.messages)
    assert "action=get_config" in messages
    assert "auth=header" in messages
    assert "user_id=alice ops" in messages
    assert "user_role=platform admin" in messages


def test_security_status_endpoint_reports_guard_health(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    monkeypatch.setenv("SHARE_LINK_SECRET", "strong-share-secret-123")
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/status",
        headers={"X-Admin-Token": "demo-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["allow_remote_clients"] is True
    assert payload["local_only_mode"] is False
    assert payload["admin_token_configured"] is True
    assert payload["remote_admin_ready"] is True
    assert payload["share_link_secret_healthy"] is True
    assert payload["remote_share_ready"] is True
    assert payload["request_id_header"] == "X-Request-ID"
    assert payload["process_time_header"] == "X-Process-Time-Ms"
    assert payload["chat_file_limits"]["max_count"] >= 1
    assert payload["document_upload_limits"]["max_count"] >= 1


def test_share_links_endpoint_lists_audit_records(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    history = chat_store.SQLiteChatMessageHistory("session-share-audit")
    history.add_user_message("share me")
    client = TestClient(api_server.app)

    created = client.post("/api/sessions/session-share-audit/share")
    assert created.status_code == 200
    share_token = created.json()["share_token"]

    listed = client.get(
        "/api/share-links",
        headers={"X-Admin-Token": "demo-admin-token"},
    )

    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] >= 1
    record = next(
        item
        for item in payload["share_links"]
        if item["resource_type"] == "session"
        and item["resource_id"] == "session-share-audit"
    )
    assert record["is_active"] is True
    assert record["share_token_preview"]
    assert record["share_token_fingerprint"]
    assert share_token not in record["share_token_fingerprint"]


def test_share_endpoints_use_current_share_secret(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api_server, "SHARE_LINK_SECRET", "stale-secret")
    monkeypatch.setenv("SHARE_LINK_SECRET", "fresh-share-secret-123456")
    history = chat_store.SQLiteChatMessageHistory("session-current-share-secret")
    history.add_user_message("share me")
    client = TestClient(api_server.app)

    created = client.post("/api/sessions/session-current-share-secret/share")

    assert created.status_code == 200
    payload = created.json()
    assert payload["share_token"] == encode_share_token(
        "session",
        "session-current-share-secret",
        "fresh-share-secret-123456",
    )

    shared_path = payload["share_url"].replace("http://testserver", "")
    shared_response = client.get(shared_path)
    assert shared_response.status_code == 200


def test_revoke_share_link_logs_fingerprint_not_raw_token(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    history = chat_store.SQLiteChatMessageHistory("session-share-log")
    history.add_user_message("share me")
    client = TestClient(api_server.app)
    created = client.post("/api/sessions/session-share-log/share")
    share_token = created.json()["share_token"]

    with caplog.at_level(logging.INFO, logger=api_server.logger.name):
        response = client.delete(
            f"/api/share-links/{share_token}",
            headers={"X-Admin-Token": "demo-admin-token"},
        )

    assert response.status_code == 200
    messages = "\n".join(caplog.messages)
    assert "action=revoke_share_link" in messages
    assert "share_token_fp=" in messages
    assert share_token not in messages
