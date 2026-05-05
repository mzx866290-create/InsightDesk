from fastapi.testclient import TestClient

import backend.api_server as api_server
from backend.stores.identity_store import SQLiteIdentityStore


def _set_remote_admin(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv(
        "APP_AUTH_TOKENS_JSON",
        '{"tokens":[{"token":"admin-token","role":"admin","user_id":"admin","auth_source":"test"},{"token":"viewer-token","role":"viewer","user_id":"viewer","auth_source":"test"}]}',
    )


def test_identity_admin_can_manage_org_user_membership(monkeypatch, tmp_path):
    store = SQLiteIdentityStore(db_path=str(tmp_path / "identity.db"))
    monkeypatch.setattr(api_server, "_identity_store", store)
    _set_remote_admin(monkeypatch)
    client = TestClient(api_server.app)

    org = client.post(
        "/api/identity/orgs",
        headers={"X-API-Token": "admin-token"},
        json={"org_id": "org-acme", "name": "Acme", "description": "Demo org"},
    )
    assert org.status_code == 200
    assert org.json()["org_id"] == "org-acme"

    user = client.post(
        "/api/identity/users",
        headers={"X-API-Token": "admin-token"},
        json={
            "user_id": "user-1",
            "display_name": "User One",
            "email": "u1@example.com",
        },
    )
    assert user.status_code == 200
    assert user.json()["email"] == "u1@example.com"

    membership = client.post(
        "/api/identity/memberships",
        headers={"X-API-Token": "admin-token"},
        json={"org_id": "org-acme", "user_id": "user-1", "role": "editor"},
    )
    assert membership.status_code == 200
    assert membership.json()["role"] == "editor"

    catalog = client.get(
        "/api/identity",
        headers={"X-API-Token": "viewer-token"},
    )
    assert catalog.status_code == 200
    payload = catalog.json()
    assert payload["organizations"][0]["org_id"] == "org-acme"
    assert payload["users"][0]["user_id"] == "user-1"
    assert payload["memberships"][0]["org_id"] == "org-acme"


def test_identity_admin_can_sync_verified_external_claims(monkeypatch, tmp_path):
    store = SQLiteIdentityStore(db_path=str(tmp_path / "identity.db"))
    monkeypatch.setattr(api_server, "_identity_store", store)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    _set_remote_admin(monkeypatch)
    store.upsert_org(
        org_id="org-acme",
        name="Acme",
        description="Demo org",
        now=1.0,
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/identity/sso/sync",
        headers={"X-API-Token": "admin-token"},
        json={
            "provider": "oidc",
            "claims": {
                "sub": "idp-user-1",
                "email": "alice@example.com",
                "name": "Alice Example",
                "groups": ["engineering"],
            },
            "allowed_domains": ["example.com"],
            "group_org_map": {"engineering": "org-acme"},
            "group_role_map": {"engineering": "editor"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["user_id"] == "oidc:idp-user-1"
    assert payload["user"]["email"] == "alice@example.com"
    assert payload["memberships"][0]["org_id"] == "org-acme"
    assert payload["memberships"][0]["role"] == "editor"
    assert payload["external"]["groups"] == ["engineering"]
    assert store.get_user("oidc:idp-user-1").display_name == "Alice Example"
    assert store.get_membership(
        org_id="org-acme",
        user_id="oidc:idp-user-1",
    ).role == "editor"
    assert any(
        event.get("action") == "sync_external_identity"
        and "memberships=1" in event.get("details", "")
        for event in api_server._security_audit_events
    )


def test_identity_sso_sync_rejects_disallowed_email_domain(monkeypatch, tmp_path):
    store = SQLiteIdentityStore(db_path=str(tmp_path / "identity.db"))
    monkeypatch.setattr(api_server, "_identity_store", store)
    _set_remote_admin(monkeypatch)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/identity/sso/sync",
        headers={"X-API-Token": "admin-token"},
        json={
            "provider": "oidc",
            "claims": {
                "sub": "idp-user-2",
                "email": "eve@external.example",
            },
            "allowed_domains": ["example.com"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "external identity email domain is not allowed"
    assert store.get_user("oidc:idp-user-2") is None


def test_identity_viewer_cannot_mutate(monkeypatch, tmp_path):
    monkeypatch.setattr(
        api_server,
        "_identity_store",
        SQLiteIdentityStore(db_path=str(tmp_path / "identity.db")),
    )
    _set_remote_admin(monkeypatch)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/identity/users",
        headers={"X-API-Token": "viewer-token"},
        json={"user_id": "user-2", "display_name": "User Two"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role: admin required."
