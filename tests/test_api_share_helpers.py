import time

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api_share_helpers import (
    SQLiteShareLinkStore,
    build_share_url,
    decode_share_token,
    encode_share_token,
)


def test_share_token_round_trip():
    token = encode_share_token("session", "session-123", "secret-value")
    assert decode_share_token(token, "secret-value") == ("session", "session-123")


def test_share_token_rejects_wrong_secret():
    token = encode_share_token("deck", "deck-123", "secret-value")

    try:
        decode_share_token(token, "wrong-secret")
    except ValueError as exc:
        assert str(exc) == "Invalid share token"
    else:
        raise AssertionError("decode_share_token should reject mismatched secrets")


def test_build_share_url_uses_request_base_url():
    app = FastAPI()

    @app.get("/probe")
    async def probe(request: Request):
        return {"share_url": build_share_url(request, "token-123")}

    client = TestClient(app)
    response = client.get("/probe")

    assert response.status_code == 200
    assert response.json()["share_url"] == "http://testserver/shared/token-123"


def test_share_link_store_supports_expiry_revoke_and_access_audit(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteShareLinkStore(db_path=str(db_path))
    now = time.time()

    record = store.upsert(
        share_token="token-123",
        resource_type="session",
        resource_id="session-1",
        expires_at=now + 60,
        created_by_ip="127.0.0.1",
        created_user_agent="pytest",
    )

    assert record.resource_type == "session"
    assert store.get_active("token-123", now=now + 1) is not None

    store.record_access(
        "token-123",
        accessed_ip="127.0.0.2",
        accessed_user_agent="browser",
    )
    accessed = store.get("token-123")
    assert accessed is not None
    assert accessed.access_count == 1
    assert accessed.last_accessed_ip == "127.0.0.2"
    assert accessed.last_accessed_user_agent == "browser"

    assert store.revoke("token-123") is True
    assert store.get_active("token-123", now=now + 2) is None


def test_share_link_store_treats_expired_link_as_inactive(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteShareLinkStore(db_path=str(db_path))
    now = time.time()

    store.upsert(
        share_token="token-expired",
        resource_type="deck",
        resource_id="deck-1",
        expires_at=now + 1,
    )

    assert store.get_active("token-expired", now=now) is not None
    assert store.get_active("token-expired", now=now + 2) is None
