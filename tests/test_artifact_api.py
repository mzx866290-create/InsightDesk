import io
from pathlib import Path

from fastapi.testclient import TestClient
from pptx import Presentation

import backend.api_server as api_server
import backend.artifact_service as artifact_service
import backend.chat_store as chat_store
import backend.deck_service as deck_service


def _history_cls_for_db(db_path: Path):
    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    return TestSQLiteChatMessageHistory


def _deck(deck_id: str = "deck-artifact") -> deck_service.DeckSpec:
    return deck_service.DeckSpec(
        deck_id=deck_id,
        meta=deck_service.DeckMeta(
            title="Board Update",
            subtitle="Q2 snapshot",
            theme="default",
            created_at="2026-04-16T10:00:00+0800",
            session_id="session-artifact",
            source_mode="chat_only",
            generator_panel_id="panel-main",
            author="tester",
            audience="leaders",
            purpose="briefing",
        ),
        generation=deck_service.DeckGeneration(
            source="chat_only",
            target_slide_count=2,
            actual_slide_count=2,
        ),
        slides=[
            deck_service.DeckSlide(
                id="cover",
                type="cover",
                title="Board Update",
                subtitle="Q2 snapshot",
                layout="hero-title",
                blocks=[],
            ),
            deck_service.DeckSlide(
                id="content-1",
                type="content",
                title="Growth Signals",
                subtitle="What changed",
                layout="title-bullets",
                blocks=[],
            ),
        ],
        source_registry=[],
    )


def _panel_config_payload(panel_id: str = "panel-main") -> dict[str, object]:
    return {
        "panel_id": panel_id,
        "connection_type": "ollama",
        "provider": "ollama",
        "model": "qwen3.5-2B:latest",
        "base_url": "http://localhost:11434",
        "api_key": "",
        "temperature": 0.3,
        "agent_mode": "auto",
    }


def test_generate_report_persists_artifact_and_supports_exports(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", history_cls)
    monkeypatch.setattr(
        api_server,
        "_artifact_store",
        artifact_service.SQLiteArtifactStore(db_path=str(db_path)),
    )

    history = history_cls("session-report-artifact")
    history.add_user_message("Board Update")
    history.add_ai_message("Revenue improved and churn declined.")

    client = TestClient(api_server.app)
    response = client.post(
        "/api/reports/generate",
        json={"session_id": "session-report-artifact"},
    )

    assert response.status_code == 200
    payload = response.json()
    artifact_id = payload["artifact_id"]
    assert artifact_id.startswith("artifact_")

    artifact_response = client.get(f"/api/artifacts/{artifact_id}")
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["artifact_type"] == "report"
    assert artifact_payload["title"] == "Board Update"
    assert artifact_payload["content"]["markdown"] == payload["markdown"]
    assert artifact_payload["available_formats"] == ["md", "pptx"]

    list_response = client.get("/api/sessions/session-report-artifact/artifacts")
    assert list_response.status_code == 200
    listed_artifacts = list_response.json()["artifacts"]
    assert [item["artifact_id"] for item in listed_artifacts] == [artifact_id]

    export_md_response = client.get(f"/api/artifacts/{artifact_id}/export?format=md")
    assert export_md_response.status_code == 200
    assert export_md_response.text == payload["markdown"]

    export_pptx_response = client.get(f"/api/artifacts/{artifact_id}/export?format=pptx")
    assert export_pptx_response.status_code == 200
    presentation = Presentation(io.BytesIO(export_pptx_response.content))
    assert len(presentation.slides) == 2
    assert presentation.slides[0].shapes.title.text == "Board Update"

    update_response = client.patch(
        f"/api/artifacts/{artifact_id}",
        json={"title": "Updated Report", "markdown": "# Updated Report"},
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["title"] == "Updated Report"
    assert updated_payload["content"]["markdown"] == "# Updated Report"


def test_create_deck_persists_artifact_and_syncs_on_update(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", history_cls)
    monkeypatch.setattr(
        api_server,
        "_artifact_store",
        artifact_service.SQLiteArtifactStore(db_path=str(db_path)),
    )
    monkeypatch.setattr(
        api_server,
        "_deck_store",
        deck_service.SQLiteDeckStore(db_path=str(db_path)),
    )

    history = history_cls("session-artifact")
    history.add_user_message("Trend scan")
    history.add_ai_message("Panel B research answer.", panel_id="panel-main")

    async def fake_build_deck(**kwargs):
        deck = _deck("deck-artifact-create")
        deck.meta.session_id = kwargs["session_id"]
        return deck

    monkeypatch.setattr(api_server, "build_deck", fake_build_deck)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/decks",
        json={
            "session_id": "session-artifact",
            "panel_config": _panel_config_payload(),
            "knowledge_base_enabled": False,
            "target_slide_count": 6,
            "theme": "default",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_id"].startswith("artifact_")

    artifact_response = client.get(f"/api/artifacts/{payload['artifact_id']}")
    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["artifact_type"] == "deck"
    assert artifact_payload["content"]["deck_id"] == "deck-artifact-create"
    assert artifact_payload["title"] == "Board Update"

    update_response = client.patch(
        "/api/decks/deck-artifact-create",
        json={"title": "Updated Board"},
    )
    assert update_response.status_code == 200

    synced_artifact_response = client.get(f"/api/artifacts/{payload['artifact_id']}")
    assert synced_artifact_response.status_code == 200
    synced_payload = synced_artifact_response.json()
    assert synced_payload["title"] == "Updated Board"

    export_response = client.get(f"/api/artifacts/{payload['artifact_id']}/export?format=pptx")
    assert export_response.status_code == 200
    exported = Presentation(io.BytesIO(export_response.content))
    assert len(exported.slides) == 2


def test_generate_artifact_endpoint_supports_report_and_deck(monkeypatch, tmp_path):
    db_path = tmp_path / "chat_history.db"
    history_cls = _history_cls_for_db(db_path)
    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", history_cls)
    monkeypatch.setattr(
        api_server,
        "_artifact_store",
        artifact_service.SQLiteArtifactStore(db_path=str(db_path)),
    )
    monkeypatch.setattr(
        api_server,
        "_deck_store",
        deck_service.SQLiteDeckStore(db_path=str(db_path)),
    )

    history = history_cls("session-generate-artifact")
    history.add_user_message("Trend scan")
    history.add_ai_message("Scoped answer.", panel_id="panel-main")

    async def fake_build_deck(**kwargs):
        deck = _deck("deck-generate-artifact")
        deck.meta.session_id = kwargs["session_id"]
        return deck

    monkeypatch.setattr(api_server, "build_deck", fake_build_deck)

    client = TestClient(api_server.app)

    report_response = client.post(
        "/api/artifacts/generate",
        json={
            "artifact_type": "report",
            "session_id": "session-generate-artifact",
        },
    )
    assert report_response.status_code == 200
    assert report_response.json()["artifact_type"] == "report"

    deck_response = client.post(
        "/api/artifacts/generate",
        json={
            "artifact_type": "deck",
            "session_id": "session-generate-artifact",
            "panel_config": _panel_config_payload(),
            "knowledge_base_enabled": False,
            "target_slide_count": 6,
            "theme": "default",
        },
    )
    assert deck_response.status_code == 200
    assert deck_response.json()["artifact_type"] == "deck"
