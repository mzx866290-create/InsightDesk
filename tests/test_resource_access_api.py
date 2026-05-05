from fastapi.testclient import TestClient

import backend.api_server as api_server
import backend.artifact_service as artifact_service
import backend.chat_store as chat_store
import backend.deck_service as deck_service
from backend.stores.identity_store import SQLiteIdentityStore
from backend.stores.resource_access_store import SQLiteResourceAccessStore
from backend.routes.resource_access_helpers import inherit_resource_grants


def _set_remote_tokens(monkeypatch):
    monkeypatch.setattr(api_server, "ALLOW_REMOTE_CLIENTS", True)
    monkeypatch.setattr(api_server, "_request_is_local", lambda request: False)
    monkeypatch.setenv(
        "APP_AUTH_TOKENS_JSON",
        '{"tokens":[{"token":"admin-token","role":"admin","user_id":"admin","auth_source":"test"},{"token":"viewer-token","role":"viewer","user_id":"viewer","auth_source":"test"},{"token":"member-token","role":"viewer","user_id":"member","auth_source":"test"},{"token":"editor-token","role":"editor","user_id":"editor","auth_source":"test"}]}',
    )


def _patch_stores(monkeypatch, tmp_path):
    identity_store = SQLiteIdentityStore(db_path=str(tmp_path / "identity.db"))
    access_store = SQLiteResourceAccessStore(db_path=str(tmp_path / "access.db"))
    monkeypatch.setattr(api_server, "_identity_store", identity_store)
    monkeypatch.setattr(api_server, "_resource_access_store", access_store)
    return identity_store, access_store


def _patch_content_stores(monkeypatch, tmp_path):
    db_path = tmp_path / "content.db"
    deck_store = deck_service.SQLiteDeckStore(db_path=str(db_path))
    artifact_store = artifact_service.SQLiteArtifactStore(db_path=str(db_path))
    monkeypatch.setattr(api_server, "_deck_store", deck_store)
    monkeypatch.setattr(api_server, "_artifact_store", artifact_store)
    return deck_store, artifact_store


def _build_deck(deck_id: str, session_id: str, title: str) -> deck_service.DeckSpec:
    return deck_service.DeckSpec(
        deck_id=deck_id,
        meta=deck_service.DeckMeta(
            title=title,
            subtitle="ACL test",
            theme="default",
            created_at="2026-04-25T10:00:00+0800",
            session_id=session_id,
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
                title=title,
                subtitle="ACL test",
                layout="hero-title",
                blocks=[],
            )
        ],
        source_registry=[],
    )


def _build_artifact(
    artifact_id: str,
    session_id: str,
    title: str,
) -> artifact_service.ArtifactRecord:
    return artifact_service.ArtifactRecord(
        artifact_id=artifact_id,
        session_id=session_id,
        artifact_type="report",
        title=title,
        status="ready",
        content={"markdown": f"# {title}", "qa_pairs": []},
    )


def test_resource_access_admin_can_grant_user_access(monkeypatch, tmp_path):
    _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    client = TestClient(api_server.app)

    grant = client.post(
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "session",
            "resource_id": "session-1",
            "user_id": "viewer",
            "role": "editor",
        },
    )
    assert grant.status_code == 200
    assert grant.json()["user_id"] == "viewer"
    assert grant.json()["role"] == "editor"

    catalog = client.get(
        "/api/access/resource-grants?resource_type=session&resource_id=session-1",
        headers={"X-API-Token": "viewer-token"},
    )
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 1

    access = client.get(
        "/api/access/resources/session/session-1/me?minimum_role=viewer",
        headers={"X-API-Token": "viewer-token"},
    )
    assert access.status_code == 200
    assert access.json()["allowed"] is True
    assert access.json()["role"] == "editor"
    assert access.json()["source"] == "user_grant"


def test_resource_access_role_matrix_documents_effective_roles(monkeypatch, tmp_path):
    _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/access/role-matrix",
        headers={"X-API-Token": "viewer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["roles"] == ["viewer", "editor", "admin", "owner"]
    assert payload["role_ranks"]["owner"] > payload["role_ranks"]["admin"]
    operations = {item["operation"]: item for item in payload["operations"]}
    assert operations["read_resource"]["roles"]["viewer"] is True
    assert operations["update_resource"]["roles"]["viewer"] is False
    assert operations["update_resource"]["roles"]["editor"] is True
    assert operations["manage_resource_grants"]["roles"]["admin"] is True
    assert operations["own_resource"]["roles"]["admin"] is False
    assert operations["own_resource"]["roles"]["owner"] is True
    assert "membership role" in payload["inheritance_rule"]


def test_resource_access_viewer_cannot_grant(monkeypatch, tmp_path):
    _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/access/resource-grants",
        headers={"X-API-Token": "viewer-token"},
        json={
            "resource_type": "session",
            "resource_id": "session-2",
            "user_id": "viewer",
            "role": "viewer",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role: admin required."


def test_resource_access_resolves_org_grant_through_membership(monkeypatch, tmp_path):
    identity_store, _access_store = _patch_stores(monkeypatch, tmp_path)
    now = 100.0
    identity_store.upsert_org(
        org_id="org-acme", name="Acme", description="Demo", now=now
    )
    identity_store.upsert_user(
        user_id="member", display_name="Member", email="", now=now
    )
    identity_store.set_membership(
        org_id="org-acme", user_id="member", role="editor", now=now
    )
    _set_remote_tokens(monkeypatch)
    client = TestClient(api_server.app)

    grant = client.post(
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "workspace",
            "resource_id": "workspace-1",
            "org_id": "org-acme",
            "role": "admin",
        },
    )
    assert grant.status_code == 200

    access = client.get(
        "/api/access/resources/workspace/workspace-1/me?minimum_role=editor",
        headers={"X-API-Token": "member-token"},
    )
    assert access.status_code == 200
    assert access.json()["allowed"] is True
    assert access.json()["role"] == "editor"
    assert access.json()["source"] == "org_grant"


def test_created_session_gets_owner_grant_and_remote_acl_filter(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    _set_remote_tokens(monkeypatch)

    db_path = tmp_path / "chat_history.db"

    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    original_get_all_sessions = chat_store.get_all_sessions
    original_update_session_meta = chat_store.update_session_meta
    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", TestSQLiteChatMessageHistory)
    monkeypatch.setattr(
        chat_store,
        "get_all_sessions",
        lambda *args, **kwargs: original_get_all_sessions(
            db_path=str(db_path),
            query=kwargs.get("query", ""),
            archived=kwargs.get("archived"),
            favorite=kwargs.get("favorite"),
            tag=kwargs.get("tag", ""),
            workspace_id=kwargs.get("workspace_id"),
        ),
    )
    monkeypatch.setattr(
        chat_store,
        "update_session_meta",
        lambda session_id, **kwargs: original_update_session_meta(
            session_id, db_path=str(db_path), **kwargs
        ),
    )
    client = TestClient(api_server.app)

    created = client.post(
        "/api/sessions",
        headers={"X-API-Token": "viewer-token"},
        json={"title": "Private session"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    grants = access_store.list_grants(
        resource_type="session", resource_id=session_id, user_id="viewer"
    )
    assert len(grants) == 1
    assert grants[0].role == "owner"
    assert any(
        event.get("action") == "resource_owner_granted"
        and "resource_type=session" in event.get("details", "")
        for event in api_server._security_audit_events
    )

    owner_list = client.get(
        "/api/sessions", headers={"X-API-Token": "viewer-token"}
    )
    assert owner_list.status_code == 200
    assert any(item["session_id"] == session_id for item in owner_list.json()["sessions"])

    other_list = client.get(
        "/api/sessions", headers={"X-API-Token": "editor-token"}
    )
    assert other_list.status_code == 200
    assert all(item["session_id"] != session_id for item in other_list.json()["sessions"])

    denied = client.patch(
        f"/api/sessions/{session_id}",
        headers={"X-API-Token": "editor-token"},
        json={"title": "Stolen"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Insufficient resource role: editor required."


def test_private_session_blocks_other_user_chat_write(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    _set_remote_tokens(monkeypatch)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="private-chat",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/chat/single",
        headers={"X-API-Token": "editor-token"},
        json={
            "session_id": "private-chat",
            "message": "hello",
            "panel_config": {"panel_id": "p1"},
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient resource role: editor required."
    assert any(
        event.get("action") == "resource_access_denied"
        and event.get("result") == "rejected"
        and "resource_id=private-chat" in event.get("details", "")
        for event in api_server._security_audit_events
    )


def test_private_session_blocks_other_user_task_create(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="private-task",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/tasks",
        headers={"X-API-Token": "editor-token"},
        json={"task_type": "web_research", "params": {}, "session_id": "private-task"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient resource role: editor required."


def test_private_session_blocks_other_user_message_and_memory_access(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="private-memory",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    client = TestClient(api_server.app)

    messages = client.get(
        "/api/sessions/private-memory/messages",
        headers={"X-API-Token": "editor-token"},
    )
    assert messages.status_code == 403
    assert messages.json()["detail"] == "Insufficient resource role: viewer required."

    memory = client.post(
        "/api/sessions/private-memory/memory/pin",
        headers={"X-API-Token": "editor-token"},
        json={"content": "secret", "kind": "fact"},
    )
    assert memory.status_code == 403
    assert memory.json()["detail"] == "Insufficient resource role: editor required."


def test_private_session_blocks_other_user_bookmark_and_share(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    monkeypatch.setenv("SHARE_LINK_SECRET", "test-share-secret-with-enough-entropy")
    access_store.upsert_grant(
        resource_type="session",
        resource_id="private-share",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    client = TestClient(api_server.app)

    bookmark = client.post(
        "/api/bookmarks",
        headers={"X-API-Token": "editor-token"},
        json={
            "session_id": "private-share",
            "role": "assistant",
            "content": "secret",
        },
    )
    assert bookmark.status_code == 403
    assert bookmark.json()["detail"] == "Insufficient resource role: editor required."

    share = client.post(
        "/api/sessions/private-share/share",
        headers={"X-API-Token": "editor-token"},
    )
    assert share.status_code == 403
    assert share.json()["detail"] == "Insufficient resource role: viewer required."


def test_inherit_resource_grants_copies_user_and_org_acl(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="source-session",
        user_id="editor",
        role="editor",
        now=1.0,
    )
    access_store.upsert_grant(
        resource_type="session",
        resource_id="source-session",
        org_id="org-acme",
        role="viewer",
        now=1.0,
    )

    copied = inherit_resource_grants(
        source_resource_type="session",
        source_resource_id="source-session",
        target_resource_type="artifact",
        target_resource_id="artifact-1",
        access_store=access_store,
        now=lambda: 2.0,
    )

    assert copied == 2
    user_grant = access_store.get_grant(
        resource_type="artifact",
        resource_id="artifact-1",
        user_id="editor",
    )
    org_grant = access_store.get_grant(
        resource_type="artifact",
        resource_id="artifact-1",
        org_id="org-acme",
    )
    assert user_grant is not None
    assert user_grant.role == "editor"
    assert org_grant is not None
    assert org_grant.role == "viewer"


def test_task_creation_inherits_session_acl(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    _set_remote_tokens(monkeypatch)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="task-source-session",
        user_id="editor",
        role="editor",
        now=1.0,
    )
    access_store.upsert_grant(
        resource_type="session",
        resource_id="task-source-session",
        org_id="org-acme",
        role="viewer",
        now=1.0,
    )
    client = TestClient(api_server.app)

    response = client.post(
        "/api/tasks",
        headers={"X-API-Token": "editor-token"},
        json={
            "task_type": "web_research",
            "params": {"query": "acl inheritance"},
            "session_id": "task-source-session",
        },
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    user_grant = access_store.get_grant(
        resource_type="task", resource_id=task_id, user_id="editor"
    )
    org_grant = access_store.get_grant(
        resource_type="task", resource_id=task_id, org_id="org-acme"
    )
    assert user_grant is not None
    assert user_grant.role == "owner"
    assert org_grant is not None
    assert org_grant.role == "viewer"
    assert any(
        event.get("action") == "resource_grants_inherited"
        and "target_type=task" in event.get("details", "")
        for event in api_server._security_audit_events
    )


def test_resource_grant_api_blocks_last_owner_downgrade_and_delete(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    monkeypatch.setattr(api_server, "_security_audit_events", [])
    _set_remote_tokens(monkeypatch)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="owner-protected",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    client = TestClient(api_server.app)

    downgrade = client.post(
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "session",
            "resource_id": "owner-protected",
            "user_id": "viewer",
            "role": "editor",
        },
    )
    assert downgrade.status_code == 409
    assert downgrade.json()["detail"] == "Cannot downgrade the last owner grant for a resource."

    delete = client.request(
        "DELETE",
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "session",
            "resource_id": "owner-protected",
            "user_id": "viewer",
        },
    )
    assert delete.status_code == 409
    assert delete.json()["detail"] == "Cannot delete the last owner grant for a resource."
    assert access_store.get_grant(
        resource_type="session", resource_id="owner-protected", user_id="viewer"
    ).role == "owner"
    assert any(
        event.get("action") == "upsert_resource_grant"
        and event.get("result") == "rejected"
        and "last_owner_downgrade_blocked" in event.get("details", "")
        for event in api_server._security_audit_events
    )
    assert any(
        event.get("action") == "delete_resource_grant"
        and event.get("result") == "rejected"
        and "last_owner_delete_blocked" in event.get("details", "")
        for event in api_server._security_audit_events
    )


def test_resource_grant_api_allows_owner_change_when_another_owner_exists(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="multi-owner",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    access_store.upsert_grant(
        resource_type="session",
        resource_id="multi-owner",
        user_id="editor",
        role="owner",
        now=1.0,
    )
    client = TestClient(api_server.app)

    downgrade = client.post(
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "session",
            "resource_id": "multi-owner",
            "user_id": "viewer",
            "role": "editor",
        },
    )
    assert downgrade.status_code == 200
    assert downgrade.json()["role"] == "editor"

    delete = client.request(
        "DELETE",
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "session",
            "resource_id": "multi-owner",
            "user_id": "editor",
        },
    )
    assert delete.status_code == 409
    assert delete.json()["detail"] == "Cannot delete the last owner grant for a resource."

    promote = client.post(
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "session",
            "resource_id": "multi-owner",
            "user_id": "viewer",
            "role": "owner",
        },
    )
    assert promote.status_code == 200

    delete = client.request(
        "DELETE",
        "/api/access/resource-grants",
        headers={"X-API-Token": "admin-token"},
        json={
            "resource_type": "session",
            "resource_id": "multi-owner",
            "user_id": "editor",
        },
    )
    assert delete.status_code == 200
    assert delete.json()["ok"] is True


def test_resource_grant_list_supports_role_subject_filters_and_pagination(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    access_store.upsert_grant(
        resource_type="session",
        resource_id="list-a",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    access_store.upsert_grant(
        resource_type="session",
        resource_id="list-b",
        user_id="editor",
        role="editor",
        now=2.0,
    )
    access_store.upsert_grant(
        resource_type="session",
        resource_id="list-c",
        org_id="org-acme",
        role="editor",
        now=3.0,
    )
    client = TestClient(api_server.app)

    role_filtered = client.get(
        "/api/access/resource-grants?role=editor&limit=1&offset=0",
        headers={"X-API-Token": "viewer-token"},
    )
    assert role_filtered.status_code == 200
    role_payload = role_filtered.json()
    assert role_payload["total"] == 2
    assert role_payload["returned"] == 1
    assert role_payload["limit"] == 1
    assert role_payload["offset"] == 0
    assert role_payload["grants"][0]["role"] == "editor"

    second_page = client.get(
        "/api/access/resource-grants?role=editor&limit=1&offset=1",
        headers={"X-API-Token": "viewer-token"},
    )
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 2
    assert second_page.json()["returned"] == 1
    assert second_page.json()["offset"] == 1

    org_filtered = client.get(
        "/api/access/resource-grants?subject_type=org",
        headers={"X-API-Token": "viewer-token"},
    )
    assert org_filtered.status_code == 200
    org_payload = org_filtered.json()
    assert org_payload["total"] == 1
    assert org_payload["returned"] == 1
    assert org_payload["grants"][0]["org_id"] == "org-acme"


def test_resource_grant_list_rejects_invalid_subject_filter(monkeypatch, tmp_path):
    _patch_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)
    client = TestClient(api_server.app)

    response = client.get(
        "/api/access/resource-grants?subject_type=team",
        headers={"X-API-Token": "viewer-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "subject_type must be user or org"


def test_global_deck_list_filters_by_resource_acl(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    deck_store, _artifact_store = _patch_content_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)

    deck_store.save(_build_deck("deck-viewer", "session-a", "Viewer Deck"))
    deck_store.save(_build_deck("deck-editor", "session-b", "Editor Deck"))
    deck_store.save(_build_deck("deck-legacy", "session-c", "Legacy Deck"))

    access_store.upsert_grant(
        resource_type="deck",
        resource_id="deck-viewer",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    access_store.upsert_grant(
        resource_type="deck",
        resource_id="deck-editor",
        user_id="editor",
        role="owner",
        now=1.0,
    )

    client = TestClient(api_server.app)

    viewer_response = client.get("/api/decks", headers={"X-API-Token": "viewer-token"})
    assert viewer_response.status_code == 200
    viewer_ids = [item["deck_id"] for item in viewer_response.json()["decks"]]
    assert "deck-viewer" in viewer_ids
    assert "deck-legacy" in viewer_ids
    assert "deck-editor" not in viewer_ids

    editor_response = client.get("/api/decks", headers={"X-API-Token": "editor-token"})
    assert editor_response.status_code == 200
    editor_ids = [item["deck_id"] for item in editor_response.json()["decks"]]
    assert "deck-editor" in editor_ids
    assert "deck-legacy" in editor_ids
    assert "deck-viewer" not in editor_ids


def test_global_artifact_list_filters_by_resource_acl(monkeypatch, tmp_path):
    _identity_store, access_store = _patch_stores(monkeypatch, tmp_path)
    _deck_store, artifact_store = _patch_content_stores(monkeypatch, tmp_path)
    _set_remote_tokens(monkeypatch)

    artifact_store.save(_build_artifact("artifact-viewer", "session-a", "Viewer Report"))
    artifact_store.save(_build_artifact("artifact-editor", "session-b", "Editor Report"))
    artifact_store.save(_build_artifact("artifact-legacy", "session-c", "Legacy Report"))

    access_store.upsert_grant(
        resource_type="artifact",
        resource_id="artifact-viewer",
        user_id="viewer",
        role="owner",
        now=1.0,
    )
    access_store.upsert_grant(
        resource_type="artifact",
        resource_id="artifact-editor",
        user_id="editor",
        role="owner",
        now=1.0,
    )

    client = TestClient(api_server.app)

    viewer_response = client.get(
        "/api/artifacts?artifact_type=report",
        headers={"X-API-Token": "viewer-token"},
    )
    assert viewer_response.status_code == 200
    viewer_ids = [item["artifact_id"] for item in viewer_response.json()["artifacts"]]
    assert "artifact-viewer" in viewer_ids
    assert "artifact-legacy" in viewer_ids
    assert "artifact-editor" not in viewer_ids

    editor_response = client.get(
        "/api/artifacts?artifact_type=report",
        headers={"X-API-Token": "editor-token"},
    )
    assert editor_response.status_code == 200
    editor_ids = [item["artifact_id"] for item in editor_response.json()["artifacts"]]
    assert "artifact-editor" in editor_ids
    assert "artifact-legacy" in editor_ids
    assert "artifact-viewer" not in editor_ids
