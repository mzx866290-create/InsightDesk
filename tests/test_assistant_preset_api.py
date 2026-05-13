from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.chat_store as chat_store
from backend.routes.assistant_preset_routes import build_assistant_preset_router


async def _noop_clear_agent_cache() -> None:
    return None


def _client_for_db(db_path) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_assistant_preset_router(
            require_remote_viewer=lambda request: {},
            require_remote_editor=lambda request: {},
            list_assistant_presets=lambda: chat_store.get_all_assistant_presets(str(db_path)),
            create_assistant_preset=lambda *args, **kwargs: chat_store.create_assistant_preset(
                *args,
                db_path=str(db_path),
                **kwargs,
            ),
            update_assistant_preset=lambda *args, **kwargs: chat_store.update_assistant_preset(
                *args,
                db_path=str(db_path),
                **kwargs,
            ),
            delete_assistant_preset=lambda preset_id: chat_store.delete_assistant_preset(
                preset_id,
                db_path=str(db_path),
            ),
            activate_assistant_preset=lambda preset_id: chat_store.activate_assistant_preset(
                preset_id,
                db_path=str(db_path),
            ),
            clear_agent_cache=_noop_clear_agent_cache,
            audit_security_event=lambda *args, **kwargs: None,
            logger=chat_store.logger,
        )
    )
    return TestClient(app)


def test_assistant_preset_crud_and_activation(tmp_path):
    client = _client_for_db(tmp_path / "chat_history.db")

    initial = client.get("/api/assistant-presets")
    assert initial.status_code == 200
    default_presets = initial.json()["presets"]
    assert len(default_presets) == 1
    assert default_presets[0]["is_active"] is True
    assert default_presets[0]["tool_config"]["mcp_servers_enabled"] == []

    create_response = client.post(
        "/api/assistant-presets",
        json={
            "name": "Research Copilot",
            "avatar": "🔎",
            "system_prompt_id": "prompt-research",
            "default_model_config": {
                "panel_id": "panel-custom",
                "provider": "deepseek",
                "connection_type": "deepseek",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "api_key": "should-not-persist",
                "temperature": 0.2,
                "agent_mode": "auto",
            },
            "tool_config": {
                "web_search_enabled": True,
                "knowledge_base_enabled": False,
                "mcp_servers_enabled": ["github", "github", "notion"],
            },
            "starters": ["查找竞品资料", "生成研究摘要"],
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["default_model_config"]["api_key"] == ""
    assert created["tool_config"]["mcp_servers_enabled"] == ["github", "notion"]

    update_response = client.put(
        f"/api/assistant-presets/{created['id']}",
        json={
            **created,
            "name": "Research Lead",
            "tool_config": {
                "web_search_enabled": False,
                "knowledge_base_enabled": True,
                "mcp_servers_enabled": [],
            },
            "starters": ["复盘这次调研"],
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Research Lead"

    activate_response = client.post(f"/api/assistant-presets/{created['id']}/activate")
    assert activate_response.status_code == 200
    active = chat_store.get_active_assistant_preset(str(tmp_path / "chat_history.db"))
    assert active and active["id"] == created["id"]

    assert client.delete(f"/api/assistant-presets/{created['id']}").status_code == 200
    remaining = client.get("/api/assistant-presets").json()["presets"]
    assert len(remaining) == 1
    assert remaining[0]["is_active"] is True
    assert client.delete(f"/api/assistant-presets/{remaining[0]['id']}").status_code == 404
