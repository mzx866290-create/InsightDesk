import importlib
import json
import logging
import time

from fastapi.testclient import TestClient

import backend.api_server as api_server
from backend.core.runtime_metrics import new_runtime_metrics_state
from backend.stores.security_audit_store import SQLiteSecurityAuditStore
from backend.stores.config_store import SQLiteAppConfigStore
from backend.stores.sso_session_store import SQLiteSsoSessionStore
from backend.helpers.share_helpers import encode_share_token
import backend.chat_store as chat_store


def _clear_auth_env(monkeypatch):
    for name in (
        "APP_AUTH_TOKENS_JSON",
        "ADMIN_API_TOKEN",
        "EDITOR_API_TOKEN",
        "VIEWER_API_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def _set_remote_mode(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)


def _set_auth_catalog(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv(
        "APP_AUTH_TOKENS_JSON",
        json.dumps(
            [
                {
                    "token": "viewer-token",
                    "user_id": "viewer.user",
                    "role": "viewer",
                    "auth_source": "viewer_catalog",
                },
                {
                    "token": "editor-token",
                    "user_id": "editor.user",
                    "role": "editor",
                    "auth_source": "editor_catalog",
                },
                {
                    "token": "admin-token",
                    "user_id": "admin.user",
                    "role": "admin",
                    "auth_source": "admin_catalog",
                },
            ]
        ),
    )


def _reset_runtime_observability(monkeypatch, *, uptime_seconds: float = 5.0):
    monkeypatch.setattr(
        api_server,
        "_runtime_started_at",
        time.time() - float(uptime_seconds),
    )
    monkeypatch.setattr(
        api_server,
        "_runtime_metrics",
        new_runtime_metrics_state(),
    )


def _reset_remote_management_rate_limit(monkeypatch):
    monkeypatch.setattr(api_server, "_remote_management_rate_limits", {})


def _reset_security_audit_events(monkeypatch, *, db_path: str | None = None):
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    monkeypatch.setattr(
        api_server,
        "_security_audit_store",
        SQLiteSecurityAuditStore(db_path=db_path) if db_path else None,
    )


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
    _clear_auth_env(monkeypatch)
    _set_remote_mode(monkeypatch)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    client = TestClient(api_server.app)

    denied = client.post("/api/agents/reset")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Missing or invalid API token."

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
    assert (
        response.json()["detail"]
        == "Remote sharing is disabled until SHARE_LINK_SECRET is strong enough."
    )


def test_remote_document_upload_requires_editor_or_admin_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _clear_auth_env(monkeypatch)
    _set_remote_mode(monkeypatch)
    monkeypatch.setenv("ADMIN_API_TOKEN", "demo-admin-token")
    client = TestClient(api_server.app)

    denied = client.post(
        "/api/documents/upload",
        files=[("files", ("demo.txt", b"hello world", "text/plain"))],
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Missing or invalid API token."

    allowed = client.post(
        "/api/documents/upload",
        headers={"X-Admin-Token": "demo-admin-token"},
        files=[("files", ("demo.txt", b"hello world", "text/plain"))],
    )
    assert allowed.status_code != 403


def test_remote_sensitive_routes_require_api_token(monkeypatch):
    _clear_auth_env(monkeypatch)
    _set_remote_mode(monkeypatch)
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
        ("get", "/api/operations/runtime", {}),
        ("get", "/api/auth/whoami", {}),
        ("get", "/api/auth/tokens", {}),
        ("get", "/api/security/audit-events", {}),
    ]

    for method, url, kwargs in cases:
        response = getattr(client, method)(url, **kwargs)
        assert response.status_code == 403, url
        assert response.json()["detail"] == "Missing or invalid API token."


def test_security_audit_logs_include_token_identity_metadata(monkeypatch, caplog):
    _set_remote_mode(monkeypatch)
    _clear_auth_env(monkeypatch)
    monkeypatch.setenv(
        "APP_AUTH_TOKENS_JSON",
        json.dumps(
            [
                {
                    "token": "viewer-token",
                    "user_id": "alice ops",
                    "role": "viewer",
                    "auth_source": "qa_catalog",
                }
            ]
        ),
    )
    client = TestClient(api_server.app)

    with caplog.at_level(logging.INFO, logger=api_server.logger.name):
        response = client.get(
            "/api/security/status",
            headers={
                "Authorization": "Bearer viewer-token",
                "X-User-Id": "spoofed-user",
                "X-User-Role": "admin",
            },
        )

    assert response.status_code == 200
    messages = "\n".join(caplog.messages)
    assert "action=get_security_status" in messages
    assert "auth=bearer" in messages
    assert "auth_source=qa_catalog" in messages
    assert "user_id=alice ops" in messages
    assert "user_role=viewer" in messages
    assert "spoofed-user" not in messages


def test_security_status_endpoint_reports_guard_health(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    _reset_security_audit_events(monkeypatch)
    monkeypatch.setenv("SHARE_LINK_SECRET", "strong-share-secret-123")
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/status",
        headers={"Authorization": "Bearer viewer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["allow_remote_clients"] is True
    assert payload["local_only_mode"] is False
    assert payload["remote_auth_ready"] is True
    assert payload["admin_token_configured"] is True
    assert payload["remote_admin_ready"] is True
    assert payload["auth_token_count"] == 3
    assert payload["configured_roles"] == ["viewer", "editor", "admin"]
    assert payload["auth_token_hygiene_healthy"] is False
    assert payload["weak_auth_token_count"] == 3
    assert payload["legacy_auth_token_count"] == 0
    assert payload["share_link_secret_healthy"] is True
    assert payload["share_link_secret_uses_default"] is False
    assert payload["share_link_secret_min_length"] == api_server.MIN_SHARE_LINK_SECRET_LENGTH
    assert payload["remote_share_ready"] is True
    assert payload["remote_management_rate_limit_enabled"] is True
    assert payload["remote_management_rate_limit_window_seconds"] >= 1
    assert payload["remote_management_rate_limit_window_seconds_source"] in {
        "default",
        "env",
        "invalid_env",
        "default_clamped",
        "env_clamped",
        "invalid_env_clamped",
    }
    assert payload["remote_management_rate_limit_max_requests"] >= 1
    assert payload["remote_management_rate_limit_max_requests_source"] in {
        "default",
        "env",
        "invalid_env",
        "default_clamped",
        "env_clamped",
        "invalid_env_clamped",
    }
    assert payload["remote_management_rate_limit_scope"] == "remote-management"
    assert payload["remote_management_rate_limit_storage"] == "memory"
    assert "/api/security/" in payload["remote_management_rate_limit_path_prefixes"]
    assert "/api/auth/" in payload["remote_management_rate_limit_path_prefixes"]
    assert "X-RateLimit-Limit" in payload["remote_management_rate_limit_response_headers"]
    assert "Retry-After" in payload["remote_management_rate_limit_response_headers"]
    assert payload["remote_management_rate_limit_tracked_principal_count"] >= 0
    assert payload["remote_management_rate_limit_active_request_count"] >= 0
    assert payload["remote_management_rate_limit_blocked_count"] >= 0
    assert payload["remote_management_rate_limit_next_reset_after_seconds"] >= 0
    assert payload["request_id_header"] == "X-Request-ID"
    assert payload["process_time_header"] == "X-Process-Time-Ms"
    assert payload["security_audit_storage"] == "sqlite"
    assert payload["security_audit_history_limit"] >= 1
    assert payload["security_audit_history_limit_source"] in {
        "default",
        "env",
        "invalid_env",
        "default_clamped",
        "env_clamped",
        "invalid_env_clamped",
    }
    assert payload["security_audit_persisted_count"] >= 0
    assert payload["security_audit_memory_window_limit"] >= 1
    assert payload["chat_file_limits"]["max_count"] >= 1
    assert payload["document_upload_limits"]["max_count"] >= 1


def test_security_status_reports_default_share_secret(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    _reset_security_audit_events(monkeypatch)
    monkeypatch.setenv("SHARE_LINK_SECRET", api_server.DEFAULT_SHARE_LINK_SECRET)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/status",
        headers={"Authorization": "Bearer viewer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["share_link_secret_healthy"] is False
    assert payload["share_link_secret_uses_default"] is True
    assert payload["share_link_secret_min_length"] == api_server.MIN_SHARE_LINK_SECRET_LENGTH
    assert payload["remote_share_ready"] is False


def test_viewer_token_can_access_status_and_whoami(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    client = TestClient(api_server.app)

    status_response = client.get(
        "/api/security/status",
        headers={"X-API-Token": "viewer-token"},
    )
    whoami_response = client.get(
        "/api/auth/whoami",
        headers={"Authorization": "Bearer viewer-token"},
    )

    assert status_response.status_code == 200
    assert whoami_response.status_code == 200
    payload = whoami_response.json()
    assert payload["user_id"] == "viewer.user"
    assert payload["role"] == "viewer"
    assert payload["auth_mode"] == "bearer"
    assert payload["auth_source"] == "viewer_catalog"
    assert payload["is_local"] is False
    assert "read_operations_runtime" in payload["capabilities"]
    assert "read_security_status" in payload["capabilities"]
    assert "manage_config" not in payload["capabilities"]


def test_admin_token_can_access_auth_token_catalog(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/auth/tokens",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["configured_roles"] == ["viewer", "editor", "admin"]
    assert payload["healthy"] is False
    assert payload["weak_count"] == 3
    assert payload["legacy_count"] == 0
    records = {item["role"]: item for item in payload["tokens"]}
    assert records["viewer"]["user_id"] == "viewer.user"
    assert records["viewer"]["auth_source"] == "viewer_catalog"
    assert records["viewer"]["token_fingerprint"]
    assert records["viewer"]["token_preview"] != "viewer-token"
    assert records["viewer"]["is_legacy"] is False
    assert records["viewer"]["is_weak"] is True
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    assert "viewer-token" not in serialized_payload
    assert "editor-token" not in serialized_payload
    assert "admin-token" not in serialized_payload


def test_auth_sso_config_reports_oidc_readiness_without_secrets(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    monkeypatch.setattr(api_server, "SSO_PROVIDER", "oidc")
    monkeypatch.setattr(api_server, "OIDC_ISSUER_URL", "https://idp.example.com")
    monkeypatch.setattr(
        api_server,
        "OIDC_AUTHORIZATION_ENDPOINT",
        "https://idp.example.com/oauth2/v1/authorize",
    )
    monkeypatch.setattr(
        api_server,
        "OIDC_TOKEN_ENDPOINT",
        "https://idp.example.com/oauth2/v1/token",
    )
    monkeypatch.setattr(
        api_server,
        "OIDC_JWKS_URL",
        "https://idp.example.com/oauth2/v1/keys",
    )
    monkeypatch.setattr(api_server, "OIDC_CLIENT_ID", "insightdesk")
    monkeypatch.setattr(api_server, "OIDC_CLIENT_SECRET", "super-secret")
    monkeypatch.setattr(api_server, "OIDC_ALLOWED_DOMAINS", "Example.com, ops.example.com")
    client = TestClient(api_server.app)

    response = client.get(
        "/api/auth/sso/config",
        headers={"X-API-Token": "viewer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["provider"] == "oidc"
    assert payload["issuer_url"] == "https://idp.example.com"
    assert payload["authorization_endpoint_configured"] is True
    assert payload["token_endpoint_configured"] is True
    assert payload["jwks_url_configured"] is True
    assert payload["client_id_configured"] is True
    assert payload["client_secret_configured"] is True
    assert payload["allowed_domains"] == ["example.com", "ops.example.com"]
    assert payload["callback_path"] == "/api/auth/sso/callback"
    assert payload["ready"] is True
    assert payload["mode"] == "oidc_configured"
    assert payload["claim_mapping"]["user_id"] == "sub"
    assert "super-secret" not in json.dumps(payload, ensure_ascii=False)


def test_admin_can_save_sso_config_without_exposing_secret(monkeypatch, tmp_path):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    for env_name in (
        "SSO_PROVIDER",
        "OIDC_ISSUER_URL",
        "OIDC_AUTHORIZATION_ENDPOINT",
        "OIDC_TOKEN_ENDPOINT",
        "OIDC_JWKS_URL",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_ALLOWED_DOMAINS",
        "OIDC_SCOPES",
        "SSO_DEFAULT_ROLE",
        "SSO_SESSION_TTL_SECONDS",
    ):
        monkeypatch.delenv(env_name, raising=False)
    config_store = SQLiteAppConfigStore(db_path=str(tmp_path / "config.db"))
    monkeypatch.setattr(api_server, "_app_config_store", config_store)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    monkeypatch.setattr(api_server, "SSO_PROVIDER", "none")
    monkeypatch.setattr(api_server, "OIDC_ISSUER_URL", "")
    monkeypatch.setattr(api_server, "OIDC_AUTHORIZATION_ENDPOINT", "")
    monkeypatch.setattr(api_server, "OIDC_TOKEN_ENDPOINT", "")
    monkeypatch.setattr(api_server, "OIDC_JWKS_URL", "")
    monkeypatch.setattr(api_server, "OIDC_CLIENT_ID", "")
    monkeypatch.setattr(api_server, "OIDC_CLIENT_SECRET", "")
    monkeypatch.setattr(api_server, "OIDC_ALLOWED_DOMAINS", "")
    monkeypatch.setattr(api_server, "OIDC_SCOPES", "openid email profile")
    monkeypatch.setattr(api_server, "SSO_DEFAULT_ROLE", "viewer")
    monkeypatch.setattr(api_server, "SSO_SESSION_TTL_SECONDS", 28800)
    client = TestClient(api_server.app)

    response = client.put(
        "/api/auth/sso/config",
        headers={"X-API-Token": "admin-token"},
        json={
            "provider": "oidc",
            "issuer_url": "https://idp.example.com",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "jwks_url": "https://idp.example.com/keys",
            "client_id": "insightdesk",
            "client_secret": "stored-secret",
            "allowed_domains": "Example.com, ops.example.com",
            "scopes": "openid email profile groups",
            "default_role": "editor",
            "session_ttl_seconds": 3600,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["provider"] == "oidc"
    assert payload["client_id"] == "insightdesk"
    assert payload["client_secret_configured"] is True
    assert payload["allowed_domains"] == ["example.com", "ops.example.com"]
    assert payload["scopes"] == ["openid", "email", "profile", "groups"]
    assert payload["default_role"] == "editor"
    assert payload["session_ttl_seconds"] == 3600
    assert "stored-secret" not in json.dumps(payload, ensure_ascii=False)
    assert config_store.get_value("sso.oidc_client_secret") == "stored-secret"
    assert any(
        event.get("action") == "update_auth_sso_config"
        for event in api_server._security_audit_events
    )


def test_auth_sso_login_builds_oidc_authorization_url(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    monkeypatch.setattr(api_server, "SSO_PROVIDER", "oidc")
    monkeypatch.setattr(
        api_server,
        "OIDC_AUTHORIZATION_ENDPOINT",
        "https://idp.example.com/oauth2/v1/authorize",
    )
    monkeypatch.setattr(api_server, "OIDC_CLIENT_ID", "insightdesk")
    monkeypatch.setattr(api_server, "OIDC_SCOPES", "openid email profile groups")
    monkeypatch.setattr(api_server, "_sso_login_states", {})
    client = TestClient(api_server.app)

    response = client.get("/api/auth/sso/login")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authorization_url"].startswith(
        "https://idp.example.com/oauth2/v1/authorize?"
    )
    assert "client_id=insightdesk" in payload["authorization_url"]
    assert "response_type=code" in payload["authorization_url"]
    assert "code_challenge_method=S256" in payload["authorization_url"]
    assert "code_verifier" not in payload
    assert payload["redirect_uri"] == "http://testserver/api/auth/sso/callback"
    assert payload["scopes"] == ["openid", "email", "profile", "groups"]
    assert payload["state"] in api_server._sso_login_states
    stored_state = api_server._sso_login_states[payload["state"]]
    assert stored_state["nonce"] == payload["nonce"]
    assert stored_state["code_verifier"]
    login_events = [
        event
        for event in api_server._security_audit_events
        if event.get("action") == "start_auth_sso_login"
    ]
    assert login_events
    login_details = login_events[-1].get("details", "")
    assert "response_mode=<default>" in login_details
    assert "state_fp=" in login_details
    assert "nonce_fp=" in login_details
    assert payload["state"] not in login_details
    assert payload["nonce"] not in login_details


def test_auth_sso_login_fragment_mode_sets_callback_response_mode(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    monkeypatch.setattr(api_server, "SSO_PROVIDER", "oidc")
    monkeypatch.setattr(
        api_server,
        "OIDC_AUTHORIZATION_ENDPOINT",
        "https://idp.example.com/oauth2/v1/authorize",
    )
    monkeypatch.setattr(api_server, "OIDC_CLIENT_ID", "insightdesk")
    monkeypatch.setattr(api_server, "_sso_login_states", {})
    client = TestClient(api_server.app)

    response = client.get("/api/auth/sso/login?response_mode=fragment")

    assert response.status_code == 200
    payload = response.json()
    assert payload["redirect_uri"] == (
        "http://testserver/api/auth/sso/callback?response_mode=fragment"
    )
    assert (
        "redirect_uri=http%3A%2F%2Ftestserver%2Fapi%2Fauth%2Fsso%2Fcallback%3Fresponse_mode%3Dfragment"
        in payload["authorization_url"]
    )


def test_auth_sso_login_requires_authorization_endpoint(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    monkeypatch.setattr(api_server, "SSO_PROVIDER", "oidc")
    monkeypatch.setattr(api_server, "OIDC_AUTHORIZATION_ENDPOINT", "")
    monkeypatch.setattr(api_server, "OIDC_CLIENT_ID", "insightdesk")
    client = TestClient(api_server.app)

    response = client.get("/api/auth/sso/login")

    assert response.status_code == 503
    assert response.json()["detail"] == "OIDC_AUTHORIZATION_ENDPOINT is required"


def test_auth_sso_callback_exchanges_code_verifies_claims_and_syncs_identity(
    monkeypatch,
    tmp_path,
):
    from backend.stores.identity_store import SQLiteIdentityStore

    _set_remote_mode(monkeypatch)
    _clear_auth_env(monkeypatch)
    store = SQLiteIdentityStore(db_path=str(tmp_path / "identity.db"))
    store.upsert_org(
        org_id="org-acme",
        name="Acme",
        description="Demo org",
        now=1.0,
    )
    monkeypatch.setattr(api_server, "_identity_store", store)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    monkeypatch.setattr(api_server, "_sso_sessions", {})
    monkeypatch.setattr(
        api_server,
        "_sso_session_store",
        SQLiteSsoSessionStore(db_path=str(tmp_path / "sso-sessions.db")),
    )
    monkeypatch.setattr(api_server, "SSO_PROVIDER", "oidc")
    monkeypatch.setattr(api_server, "SSO_DEFAULT_ROLE", "viewer")
    monkeypatch.setattr(api_server, "OIDC_ALLOWED_DOMAINS", "example.com")
    monkeypatch.setattr(
        api_server,
        "_sso_login_states",
        {
            "state-1": {
                "created_at": api_server.time.time(),
                "nonce": "nonce-1",
                "code_verifier": "verifier-1",
                "redirect_uri": "http://testserver/api/auth/sso/callback",
            }
        },
    )

    async def fake_exchange_oidc_code(*, code, redirect_uri, code_verifier):
        assert code == "auth-code"
        assert redirect_uri == "http://testserver/api/auth/sso/callback"
        assert code_verifier == "verifier-1"
        return {"id_token": "id-token", "token_type": "Bearer", "expires_in": 3600}

    def fake_verify_oidc_id_token(id_token, *, nonce):
        assert id_token == "id-token"
        assert nonce == "nonce-1"
        return {
            "sub": "idp-user-3",
            "email": "carol@example.com",
            "name": "Carol Example",
            "groups": [],
        }

    monkeypatch.setattr(api_server, "_exchange_oidc_code", fake_exchange_oidc_code)
    monkeypatch.setattr(api_server, "_verify_oidc_id_token", fake_verify_oidc_id_token)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/auth/sso/callback",
        params={"code": "auth-code", "state": "state-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_source"] == "oidc"
    assert payload["token_type"] == "Bearer"
    assert payload["expires_in"] == 3600
    assert payload["app_session_token"].startswith("sso_")
    assert payload["app_session_expires_at"] > api_server.time.time()
    assert payload["role"] == "viewer"
    assert payload["user"]["user_id"] == "oidc:idp-user-3"
    assert payload["user"]["email"] == "carol@example.com"
    assert "state-1" not in api_server._sso_login_states
    assert store.get_user("oidc:idp-user-3").display_name == "Carol Example"
    callback_events = [
        event
        for event in api_server._security_audit_events
        if event.get("action") == "complete_auth_sso_callback"
        and event.get("result") == "ok"
    ]
    assert callback_events
    callback_details = callback_events[-1].get("details", "")
    assert "provider=oidc" in callback_details
    assert "user_id=oidc:idp-user-3" in callback_details
    assert "role=viewer" in callback_details
    assert "memberships=0" in callback_details
    assert "groups=0" in callback_details
    assert "token_type=Bearer" in callback_details
    assert "expires_in=3600" in callback_details
    assert "app_session_expires_at=" in callback_details
    assert "app_session_token_fp=" in callback_details
    assert payload["app_session_token"] not in callback_details

    whoami = client.get(
        "/api/auth/whoami",
        headers={"Authorization": f"Bearer {payload['app_session_token']}"},
    )
    assert whoami.status_code == 200
    assert whoami.json()["user_id"] == "oidc:idp-user-3"
    assert whoami.json()["role"] == "viewer"
    assert whoami.json()["auth_source"] == "sso_oidc"


def test_auth_sso_callback_rejects_invalid_state(monkeypatch):
    monkeypatch.setattr(api_server, "_sso_login_states", {})
    client = TestClient(api_server.app)

    response = client.get(
        "/api/auth/sso/callback",
        params={"code": "auth-code", "state": "missing"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired SSO state"


def test_auth_sso_callback_fragment_mode_writes_session_storage(monkeypatch, tmp_path):
    from backend.stores.identity_store import SQLiteIdentityStore

    _set_remote_mode(monkeypatch)
    _clear_auth_env(monkeypatch)
    store = SQLiteIdentityStore(db_path=str(tmp_path / "identity.db"))
    monkeypatch.setattr(api_server, "_identity_store", store)
    monkeypatch.setattr(api_server, "_sso_sessions", {})
    monkeypatch.setattr(
        api_server,
        "_sso_session_store",
        SQLiteSsoSessionStore(db_path=str(tmp_path / "sso-sessions.db")),
    )
    monkeypatch.setattr(api_server, "SSO_PROVIDER", "oidc")
    monkeypatch.setattr(api_server, "OIDC_ALLOWED_DOMAINS", "example.com")
    monkeypatch.setattr(
        api_server,
        "_sso_login_states",
        {
            "state-html": {
                "created_at": api_server.time.time(),
                "nonce": "nonce-html",
                "code_verifier": "verifier-html",
                "redirect_uri": (
                    "http://testserver/api/auth/sso/callback?response_mode=fragment"
                ),
            }
        },
    )

    async def fake_exchange_oidc_code(*, code, redirect_uri, code_verifier):
        return {"id_token": "id-token", "token_type": "Bearer"}

    def fake_verify_oidc_id_token(id_token, *, nonce):
        return {
            "sub": "idp-html",
            "email": "html@example.com",
            "name": "Html User",
            "groups": [],
        }

    monkeypatch.setattr(api_server, "_exchange_oidc_code", fake_exchange_oidc_code)
    monkeypatch.setattr(api_server, "_verify_oidc_id_token", fake_verify_oidc_id_token)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/auth/sso/callback",
        params={"code": "auth-code", "state": "state-html", "response_mode": "fragment"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "sessionStorage.setItem('api_token', 'sso_" in response.text
    assert "window.location.replace('/')" in response.text


def test_sso_session_token_survives_in_memory_cache_reset(monkeypatch, tmp_path):
    _set_remote_mode(monkeypatch)
    _clear_auth_env(monkeypatch)
    monkeypatch.setattr(
        api_server,
        "_sso_session_store",
        SQLiteSsoSessionStore(db_path=str(tmp_path / "sso-sessions.db")),
    )
    monkeypatch.setattr(api_server, "_sso_sessions", {})
    monkeypatch.setattr(api_server, "SSO_DEFAULT_ROLE", "viewer")
    client = TestClient(api_server.app)

    issued = api_server._issue_sso_session_token(
        user_id="oidc:persisted-user",
        role="viewer",
    )
    monkeypatch.setattr(api_server, "_sso_sessions", {})

    whoami = client.get(
        "/api/auth/whoami",
        headers={"Authorization": f"Bearer {issued['token']}"},
    )

    assert whoami.status_code == 200
    assert whoami.json()["user_id"] == "oidc:persisted-user"
    assert whoami.json()["role"] == "viewer"
    assert whoami.json()["auth_source"] == "sso_oidc"


def test_legacy_auth_token_is_flagged_in_catalog(monkeypatch):
    _clear_auth_env(monkeypatch)
    _set_remote_mode(monkeypatch)
    monkeypatch.setenv("ADMIN_API_TOKEN", "legacy-admin-token-123456")
    client = TestClient(api_server.app)

    response = client.get(
        "/api/auth/tokens",
        headers={"X-Admin-Token": "legacy-admin-token-123456"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["healthy"] is False
    assert payload["weak_count"] == 0
    assert payload["legacy_count"] == 1
    assert payload["configured_roles"] == ["admin"]
    assert payload["tokens"][0]["auth_source"] == "legacy_admin_token"
    assert payload["tokens"][0]["is_legacy"] is True
    assert payload["tokens"][0]["is_weak"] is False


def test_viewer_token_cannot_access_auth_token_catalog(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/auth/tokens",
        headers={"Authorization": "Bearer viewer-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role: admin required."


def test_viewer_token_can_access_runtime_operations(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    _reset_runtime_observability(monkeypatch, uptime_seconds=8)
    client = TestClient(api_server.app)

    health_response = client.get("/api/health")
    assert health_response.status_code == 200

    response = client.get(
        "/api/operations/runtime",
        headers={"Authorization": "Bearer viewer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uptime_seconds"] >= 8
    assert payload["request_metrics"]["total_requests"] >= 1
    assert payload["request_metrics"]["by_status_class"]["2xx"] >= 1
    assert payload["task_summary"]["in_memory_total"] >= 0
    assert payload["task_summary"]["running"] >= 0
    assert payload["security"]["configured_roles"] == ["viewer", "editor", "admin"]


def test_remote_management_rate_limit_blocks_repeated_admin_requests(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    _reset_security_audit_events(monkeypatch)
    _reset_remote_management_rate_limit(monkeypatch)
    monkeypatch.setattr(api_server, "REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS", 2)
    monkeypatch.setattr(api_server, "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(api_server, "REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED", True)
    client = TestClient(api_server.app)

    first = client.get(
        "/api/auth/tokens",
        headers={"Authorization": "Bearer admin-token"},
    )
    second = client.get(
        "/api/auth/tokens",
        headers={"Authorization": "Bearer admin-token"},
    )
    third = client.get(
        "/api/auth/tokens",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["code"] == "RATE_LIMIT"
    assert third.headers["X-RateLimit-Limit"] == "2"
    assert third.headers["X-RateLimit-Remaining"] == "0"
    assert third.headers["X-RateLimit-Scope"] == "remote-management"
    assert int(third.headers["Retry-After"]) >= 1
    status = client.get(
        "/api/security/status",
        headers={"Authorization": "Bearer admin-token"},
    )
    assert status.status_code == 429
    direct_payload = api_server._security_status_payload()
    assert direct_payload["remote_management_rate_limit_tracked_principal_count"] >= 1
    assert direct_payload["remote_management_rate_limit_blocked_count"] >= 1
    assert direct_payload["remote_management_rate_limit_last_blocked_at"] is not None
    assert direct_payload["remote_management_rate_limit_next_reset_after_seconds"] >= 1
    assert any(
        item["action"] == "remote_management_rate_limit" and item["result"] == "blocked"
        for item in api_server._security_audit_events
    )


def test_remote_management_rate_limit_status_prunes_expired_principals(monkeypatch):
    _reset_remote_management_rate_limit(monkeypatch)
    monkeypatch.setattr(api_server, "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS", 60)
    now = {"value": 1_000.0}
    monkeypatch.setattr(api_server.time, "time", lambda: now["value"])
    monkeypatch.setattr(
        api_server,
        "_remote_management_rate_limits",
        {
            "expired": {
                "window_started_at": 900.0,
                "count": 4.0,
                "blocked_count": 2.0,
                "last_blocked_at": 905.0,
            },
            "active": {
                "window_started_at": 970.0,
                "count": 1.0,
            },
        },
    )

    status = api_server._remote_management_rate_limit_status()

    assert "expired" not in api_server._remote_management_rate_limits
    assert status["tracked_principal_count"] == 1
    assert status["active_request_count"] == 1
    assert status["blocked_count"] == 0
    assert status["last_blocked_at"] is None
    assert status["next_reset_after_seconds"] == 30

    now["value"] = 1_031.0
    expired_status = api_server._remote_management_rate_limit_status()

    assert api_server._remote_management_rate_limits == {}
    assert expired_status["tracked_principal_count"] == 0
    assert expired_status["active_request_count"] == 0
    assert expired_status["blocked_count"] == 0
    assert expired_status["last_blocked_at"] is None
    assert expired_status["next_reset_after_seconds"] == 0


def test_local_requests_bypass_remote_management_rate_limit(monkeypatch):
    _clear_auth_env(monkeypatch)
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    _reset_remote_management_rate_limit(monkeypatch)
    monkeypatch.setattr(api_server, "REMOTE_MANAGEMENT_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(api_server, "REMOTE_MANAGEMENT_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(api_server, "REMOTE_MANAGEMENT_RATE_LIMIT_ENABLED", True)
    client = TestClient(api_server.app)

    first = client.get("/api/config")
    second = client.get("/api/config")

    assert first.status_code == 200
    assert second.status_code == 200
    assert "X-RateLimit-Limit" not in first.headers
    assert "X-RateLimit-Limit" not in second.headers


def test_runtime_operations_reports_recent_errors(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    _reset_runtime_observability(monkeypatch)
    original_security_status_payload = api_server._security_status_payload
    state = {"should_fail": True}

    def flaky_security_status_payload():
        if state["should_fail"]:
            raise RuntimeError("runtime\nboom\ttoken=123")
        return original_security_status_payload()

    monkeypatch.setattr(
        api_server,
        "_security_status_payload",
        flaky_security_status_payload,
    )
    client = TestClient(api_server.app, raise_server_exceptions=False)

    failed_response = client.get(
        "/api/security/status",
        headers={"X-API-Token": "viewer-token"},
    )
    state["should_fail"] = False
    runtime_response = client.get(
        "/api/operations/runtime",
        headers={"X-API-Token": "viewer-token"},
    )

    assert failed_response.status_code == 500
    assert runtime_response.status_code == 200
    payload = runtime_response.json()
    assert payload["request_metrics"]["total_errors"] >= 1
    assert payload["request_metrics"]["by_status_class"]["5xx"] >= 1
    assert payload["recent_errors"]
    recent_error = payload["recent_errors"][-1]
    assert recent_error["path"] == "/api/security/status"
    assert recent_error["method"] == "GET"
    assert recent_error["status_code"] == 500
    assert recent_error["error_code"] == "INTERNAL_ERROR"
    assert recent_error["message"] == "runtime boom token=123"


def test_viewer_token_cannot_access_admin_routes(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/config",
        headers={"X-API-Token": "viewer-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role: admin required."


def test_admin_token_can_read_security_audit_events(monkeypatch, tmp_path):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    _reset_security_audit_events(
        monkeypatch,
        db_path=str(tmp_path / "chat_history.db"),
    )
    client = TestClient(api_server.app)

    status_response = client.get(
        "/api/security/status",
        headers={"Authorization": "Bearer viewer-token"},
    )
    assert status_response.status_code == 200
    monkeypatch.setattr(api_server, "_security_audit_events", [])

    audit_response = client.get(
        "/api/security/audit-events",
        headers={"X-API-Token": "admin-token"},
        params={"limit": 10, "action": "get_security_status"},
    )

    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["limit"] == 10
    assert payload["total"] >= 1
    event = payload["events"][-1]
    assert event["action"] == "get_security_status"
    assert event["result"] == "ok"
    assert event["auth_mode"] == "bearer"
    assert event["auth_source"] == "viewer_catalog"
    assert event["user_id"] == "viewer.user"
    assert event["user_role"] == "viewer"


def test_viewer_token_cannot_read_security_audit_events(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-events",
        headers={"X-API-Token": "viewer-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role: admin required."


def test_admin_can_cleanup_security_audit_events(monkeypatch, tmp_path):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    _reset_security_audit_events(
        monkeypatch,
        db_path=str(tmp_path / "chat_history.db"),
    )
    client = TestClient(api_server.app)

    for _ in range(3):
        response = client.get(
            "/api/security/status",
            headers={"Authorization": "Bearer viewer-token"},
        )
        assert response.status_code == 200

    cleanup_response = client.post(
        "/api/security/audit-events/cleanup",
        headers={"X-API-Token": "admin-token"},
        params={"keep_latest": 1},
    )

    assert cleanup_response.status_code == 200
    payload = cleanup_response.json()
    assert payload["keep_latest"] == 1
    assert payload["deleted_count"] == 2
    assert payload["remaining_count"] == 2
    assert payload["memory_deleted_count"] == 2
    assert payload["memory_remaining_count"] == 2
    assert payload["includes_cleanup_event"] is True

    stored_actions = [
        event.action for event in api_server._get_security_audit_store().list_events(limit=10)
    ]
    assert stored_actions == [
        "get_security_status",
        "cleanup_security_audit_events",
    ]


def test_admin_can_list_access_audit_action_catalog(monkeypatch):
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/security/audit-actions",
        headers={"X-API-Token": "admin-token"},
        params={"category": "access"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert "access" in payload["categories"]
    actions = {item["action"]: item for item in payload["actions"]}
    assert "upsert_resource_grant" in actions
    assert "delete_resource_grant" in actions
    assert actions["resource_access_denied"]["category"] == "access"
    assert actions["resource_access_denied"]["minimum_reader_role"] == "admin"


def test_invalid_security_audit_history_limit_env_falls_back_safely(monkeypatch):
    monkeypatch.setenv("SECURITY_AUDIT_HISTORY_LIMIT", "not-a-number")
    importlib.reload(api_server)

    assert api_server.SECURITY_AUDIT_HISTORY_LIMIT == 2000
    assert api_server.SECURITY_AUDIT_HISTORY_LIMIT_SOURCE == "invalid_env"
    assert (
        api_server._security_status_payload()["security_audit_history_limit_source"]
        == "invalid_env"
    )

    monkeypatch.setenv("SECURITY_AUDIT_HISTORY_LIMIT", "-5")
    importlib.reload(api_server)

    assert api_server.SECURITY_AUDIT_HISTORY_LIMIT == 1
    assert api_server.SECURITY_AUDIT_HISTORY_LIMIT_SOURCE == "env_clamped"
    assert api_server._security_status_payload()["security_audit_history_limit"] == 1

    monkeypatch.delenv("SECURITY_AUDIT_HISTORY_LIMIT", raising=False)
    importlib.reload(api_server)


def test_editor_token_can_manage_prompts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _set_remote_mode(monkeypatch)
    _set_auth_catalog(monkeypatch)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/prompts",
        headers={"X-API-Token": "editor-token"},
        json={"name": "Operations", "content": "Use the current SOP."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Operations"
    assert payload["content"] == "Use the current SOP."


def test_share_links_endpoint_lists_audit_records(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _clear_auth_env(monkeypatch)
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


def test_revoke_share_link_logs_fingerprint_not_raw_token(
    monkeypatch, tmp_path, caplog
):
    monkeypatch.chdir(tmp_path)
    _clear_auth_env(monkeypatch)
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
