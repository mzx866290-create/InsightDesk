from fastapi.testclient import TestClient

import api_server
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
