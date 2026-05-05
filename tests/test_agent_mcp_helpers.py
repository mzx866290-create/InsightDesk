import asyncio
import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.agent_mcp_helpers import (
    add_mcp_approved_connector,
    approve_runtime_mcp_connector,
    build_mcp_connector_marketplace,
    build_mcp_runtime_monitor_payload,
    clear_mcp_runtime_health_history,
    clear_runtime_mcp_approved_connectors,
    current_mcp_server_config_payload,
    current_mcp_approved_connector_names,
    default_mcp_connections,
    default_mcp_server_names,
    evaluate_mcp_connector_policy,
    get_mcp_runtime_health_history,
    list_mcp_approved_connectors,
    list_mcp_server_health,
    list_mcp_server_catalog,
    list_mcp_server_runtime_health,
    load_mcp_connection_config,
    load_mcp_tool_overrides,
    normalize_mcp_approved_connectors,
    save_mcp_server_config_payload,
    record_mcp_runtime_health_snapshot,
    remove_mcp_approved_connector,
    select_mcp_connections,
    summarize_mcp_runtime_health,
)
from backend.api_config_store import (
    SQLiteAppConfigStore,
    append_mcp_runtime_health_history,
    read_mcp_runtime_health_history,
)
from backend.routes.operations_routes import build_operations_router


class _RuntimeOperationsResponse(BaseModel):
    pass


async def _noop_async(*_args, **_kwargs):
    return None


def _mcp_config_api_client(clear_calls: list[str]):
    async def _clear_agent_cache():
        clear_calls.append("cleared")

    app = FastAPI()
    app.include_router(
        build_operations_router(
            runtime_operations_response_model=_RuntimeOperationsResponse,
            require_remote_viewer=lambda _request: {},
            require_remote_admin=lambda _request: {},
            runtime_request_metrics_payload=lambda: {},
            runtime_task_summary_payload=lambda: {},
            runtime_operations_payload=lambda: {},
            get_runtime_started_at=lambda: 0.0,
            sync_runtime_secret_from_store=lambda _env_name, _config_key: "",
            validate_tavily_api_key=_noop_async,
            get_app_config_store=lambda: object(),
            upsert_cloud_model_api_key=lambda api_key_ref, _api_key: api_key_ref or "key-ref",
            delete_cloud_model_api_key=lambda _api_key_ref: False,
            clear_agent_cache=_clear_agent_cache,
            audit_security_event=lambda *_args, **_kwargs: None,
        )
    )
    return TestClient(app)


def test_default_mcp_connections_discovers_repo_scripts(tmp_path):
    mcp_dir = tmp_path / "mcp_servers"
    mcp_dir.mkdir()
    (mcp_dir / "knowledge_server.py").write_text("print('knowledge')", encoding="utf-8")
    (mcp_dir / "search_server.py").write_text("print('search')", encoding="utf-8")

    connections = default_mcp_connections(
        project_root=tmp_path,
        python_command="python",
    )

    assert set(connections) == {"knowledge-base", "web-search"}
    assert connections["knowledge-base"]["args"] == [
        str((mcp_dir / "knowledge_server.py").resolve())
    ]
    assert connections["web-search"]["cwd"] == str(tmp_path)


def test_load_mcp_connection_config_resolves_relative_paths(tmp_path):
    config_path = tmp_path / "config" / "mcp.json"
    config_path.parent.mkdir()
    server_script = tmp_path / "servers" / "custom_server.py"
    server_script.parent.mkdir()
    server_script.write_text("print('server')", encoding="utf-8")
    (tmp_path / "runtime").mkdir()

    config_path.write_text(
        json.dumps(
            {
                "custom": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["../servers/custom_server.py"],
                    "cwd": "../runtime",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    connections = load_mcp_connection_config(str(config_path), project_root=tmp_path)

    assert connections["custom"]["args"] == [str(server_script.resolve())]
    assert connections["custom"]["cwd"] == str((tmp_path / "runtime").resolve())


def test_mcp_server_config_payload_redacts_sensitive_env_and_headers(tmp_path):
    config_path = tmp_path / "mcp.json"

    payload = save_mcp_server_config_payload(
        {
            "servers": {
                "custom": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["server.py"],
                    "env": {
                        "API_TOKEN": "raw-token",
                        "PUBLIC_LABEL": "still-sensitive-in-env",
                    },
                    "headers": {
                        "Authorization": "Bearer raw-auth",
                        "X-Trace": "trace-value",
                    },
                    "metadata": {"label": "Custom"},
                }
            }
        },
        project_root=tmp_path,
        config_path=str(config_path),
    )

    rendered = json.dumps(payload, ensure_ascii=False)
    assert "raw-token" not in rendered
    assert "Bearer raw-auth" not in rendered
    assert "trace-value" not in rendered
    assert payload["servers"]["custom"]["env"] == {
        "API_TOKEN": "***redacted***",
        "PUBLIC_LABEL": "***redacted***",
    }
    assert payload["servers"]["custom"]["headers"] == {
        "Authorization": "***redacted***",
        "X-Trace": "***redacted***",
    }
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["custom"]["env"]["API_TOKEN"] == "raw-token"
    assert persisted["custom"]["headers"]["Authorization"] == "Bearer raw-auth"


def test_mcp_server_config_save_preserves_existing_redacted_values(tmp_path):
    config_path = tmp_path / "mcp.json"
    save_mcp_server_config_payload(
        {
            "servers": {
                "custom": {
                    "transport": "stdio",
                    "command": "python",
                    "env": {"API_TOKEN": "original-token"},
                }
            }
        },
        project_root=tmp_path,
        config_path=str(config_path),
    )

    save_mcp_server_config_payload(
        {
            "servers": {
                "custom": {
                    "transport": "stdio",
                    "command": "python",
                    "env": {"API_TOKEN": "***redacted***"},
                }
            }
        },
        project_root=tmp_path,
        config_path=str(config_path),
    )

    payload = current_mcp_server_config_payload(
        project_root=tmp_path,
        config_path=str(config_path),
    )
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["custom"]["env"]["API_TOKEN"] == "original-token"
    assert payload["servers"]["custom"]["env"]["API_TOKEN"] == "***redacted***"


def test_mcp_server_config_api_hot_update_redacts_and_clears_agent_cache(
    monkeypatch,
    tmp_path,
):
    config_path = tmp_path / "mcp.json"
    monkeypatch.setenv("MCP_SERVER_CONFIG_PATH", str(config_path))
    clear_calls: list[str] = []
    client = _mcp_config_api_client(clear_calls)

    response = client.put(
        "/api/connectors/mcp/config",
        json={
            "servers": {
                "notification": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["notify.py"],
                    "headers": {"Authorization": "Bearer notify-token"},
                }
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "config"
    assert payload["servers"]["notification"]["headers"]["Authorization"] == (
        "***redacted***"
    )
    assert clear_calls == ["cleared"]
    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["notification"]["headers"]["Authorization"] == "Bearer notify-token"

    follow_up = client.get("/api/connectors/mcp/config")
    assert follow_up.status_code == 200
    follow_up_payload = follow_up.json()
    assert follow_up_payload["servers"] == payload["servers"]
    assert follow_up_payload["connectors"][0]["name"] == "notification"
    assert follow_up_payload["marketplace"]["summary"]["total"] == 1
    assert follow_up_payload["hot_update"] == {
        "enabled": True,
        "applied": False,
        "requires_agent_cache_clear": False,
        "restart_required": False,
    }


def test_mcp_config_payload_includes_marketplace_and_hot_update_contract(tmp_path):
    config_path = tmp_path / "mcp.json"

    payload = save_mcp_server_config_payload(
        {
            "servers": {
                "crm-sync": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["crm.py"],
                    "metadata": {
                        "label": "CRM Sync",
                        "category": "crm",
                        "risk_level": "high",
                        "requires_approval": True,
                    },
                }
            }
        },
        project_root=tmp_path,
        config_path=str(config_path),
    )

    assert payload["hot_update"] == {
        "enabled": True,
        "applied": True,
        "changed": True,
        "requires_agent_cache_clear": True,
        "restart_required": False,
    }
    assert payload["default_enabled"] == default_mcp_server_names()
    assert payload["connectors"][0]["name"] == "crm-sync"
    assert payload["marketplace"]["summary"]["total"] == 1
    assert payload["marketplace"]["summary"]["requires_approval"] == 1
    assert payload["marketplace"]["categories"][0]["id"] == "crm"


def test_select_mcp_connections_honors_enablement_and_server_filters(monkeypatch, tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "knowledge-base": {"transport": "stdio", "command": "python", "args": ["kb.py"]},
                "web-search": {"transport": "stdio", "command": "python", "args": ["web.py"]},
                "custom": {"transport": "stdio", "command": "python", "args": ["custom.py"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("ENABLE_MCP_TOOLS", "true")
    monkeypatch.setenv("MCP_SERVER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ENABLED_MCP_SERVERS", "web-search, custom, missing")
    monkeypatch.setenv("MCP_APPROVED_CONNECTORS", "custom")

    connections = select_mcp_connections(
        knowledge_base_enabled=False,
        web_search_enabled=True,
        project_root=tmp_path,
    )

    assert set(connections) == {"web-search", "custom"}


def test_select_mcp_connections_supports_explicit_enabled_servers_without_env(monkeypatch, tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "knowledge-base": {"transport": "stdio", "command": "python", "args": ["kb.py"]},
                "custom": {"transport": "stdio", "command": "python", "args": ["custom.py"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("ENABLE_MCP_TOOLS", raising=False)
    monkeypatch.delenv("ENABLED_MCP_SERVERS", raising=False)

    connections = select_mcp_connections(
        knowledge_base_enabled=True,
        web_search_enabled=False,
        project_root=tmp_path,
        config_path=str(config_path),
        enabled_server_names=["custom", "missing"],
        approved_connector_names=["custom"],
    )

    assert set(connections) == {"custom"}


def test_list_mcp_server_catalog_includes_default_source_and_metadata(tmp_path):
    mcp_dir = tmp_path / "mcp_servers"
    mcp_dir.mkdir()
    (mcp_dir / "knowledge_server.py").write_text("print('knowledge')", encoding="utf-8")
    (mcp_dir / "search_server.py").write_text("print('search')", encoding="utf-8")

    catalog = list_mcp_server_catalog(
        project_root=tmp_path,
        python_command="python",
    )

    assert [item["name"] for item in catalog] == ["knowledge-base", "web-search"]
    assert all(item["source"] == "default" for item in catalog)
    assert catalog[0]["label"] == "Knowledge Base"
    assert catalog[1]["label"] == "Web Search"
    by_name = {item["name"]: item for item in catalog}
    assert by_name["knowledge-base"]["capability_scopes"] == [
        "knowledge:read",
        "knowledge:diagnostics",
    ]
    assert by_name["knowledge-base"]["risk_level"] == "low"
    assert by_name["knowledge-base"]["requires_approval"] is False
    assert by_name["knowledge-base"]["config_schema"] == {
        "transport": "stdio",
        "required": ["command"],
        "optional": ["transport", "args", "cwd", "encoding", "env"],
        "sensitive": ["env"],
    }
    assert by_name["web-search"]["capability_scopes"] == ["web:search", "web:fetch"]
    assert by_name["web-search"]["risk_level"] == "medium"
    assert by_name["web-search"]["requires_approval"] is False
    assert all(item["configured"] for item in catalog)
    assert all(item["status"] == "disabled" for item in catalog)
    assert all("mcp_tools_disabled" in item["status_reasons"] for item in catalog)


def test_builtin_connector_catalog_includes_database_calendar_notification(tmp_path):
    mcp_dir = tmp_path / "mcp_servers"
    mcp_dir.mkdir()
    for script_name in (
        "knowledge_server.py",
        "search_server.py",
        "database_server.py",
        "calendar_server.py",
        "notification_server.py",
    ):
        (mcp_dir / script_name).write_text("print('server')", encoding="utf-8")

    catalog = list_mcp_server_catalog(
        project_root=tmp_path,
        python_command="python",
    )

    by_name = {item["name"]: item for item in catalog}
    assert set(by_name) == {
        "calendar",
        "database",
        "knowledge-base",
        "notification",
        "web-search",
    }
    assert by_name["database"]["category"] == "data"
    assert by_name["database"]["capability_scopes"] == ["database:read"]
    assert by_name["calendar"]["category"] == "productivity"
    assert by_name["calendar"]["risk_level"] == "low"
    assert by_name["notification"]["category"] == "communication"
    assert by_name["notification"]["config_schema"]["sensitive"] == ["env", "headers"]
    assert all(by_name[name]["builtin"] is True for name in by_name)


def test_list_mcp_server_catalog_includes_custom_config_metadata(tmp_path):
    server_script = tmp_path / "custom_server.py"
    server_script.write_text("print('custom')", encoding="utf-8")
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "crm-sync": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["custom_server.py"],
                    "cwd": ".",
                    "metadata": {
                        "label": "CRM Sync",
                        "description": "Read and update CRM records.",
                        "category": "crm",
                        "capability_scopes": ["crm:read", "crm:write", "crm:read"],
                        "risk_level": "high",
                        "requires_approval": True,
                        "config_schema": {
                            "transport": "stdio",
                            "required_fields": ["command"],
                            "optional_fields": ["transport", "args", "cwd", "env"],
                            "sensitive_fields": ["env.CRM_TOKEN"],
                        },
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    catalog = list_mcp_server_catalog(
        project_root=tmp_path,
        config_path=str(config_path),
        enable_mcp_tools=True,
        enabled_server_names=["crm-sync"],
    )

    assert len(catalog) == 1
    connector = catalog[0]
    assert connector["name"] == "crm-sync"
    assert connector["label"] == "CRM Sync"
    assert connector["description"] == "Read and update CRM records."
    assert connector["category"] == "crm"
    assert connector["builtin"] is False
    assert connector["source"] == "config"
    assert connector["enabled"] is True
    assert connector["healthy"] is True
    assert connector["capability_scopes"] == ["crm:read", "crm:write"]
    assert connector["risk_level"] == "high"
    assert connector["requires_approval"] is True
    assert connector["policy"]["allowed"] is False
    assert connector["policy"]["requires_approval"] is True
    assert "connector_not_approved" in connector["policy"]["reasons"]
    assert connector["config_schema"] == {
        "transport": "stdio",
        "required": ["command"],
        "optional": ["transport", "args", "cwd", "env"],
        "sensitive": ["env.CRM_TOKEN"],
    }

    selected = select_mcp_connections(
        project_root=tmp_path,
        config_path=str(config_path),
        enable_mcp_tools=True,
        enabled_server_names=["crm-sync"],
    )
    assert selected == {}

    approved_selected = select_mcp_connections(
        project_root=tmp_path,
        config_path=str(config_path),
        enable_mcp_tools=True,
        enabled_server_names=["crm-sync"],
        approved_connector_names=["crm-sync"],
    )
    assert "metadata" not in approved_selected["crm-sync"]


def test_evaluate_mcp_connector_policy_allows_low_risk_connector_by_default():
    policy = evaluate_mcp_connector_policy("knowledge-base")

    assert policy["allowed"] is True
    assert policy["requires_approval"] is False
    assert policy["reasons"] == []
    assert policy["capability_scopes"] == [
        "knowledge:read",
        "knowledge:diagnostics",
    ]
    assert policy["risk_level"] == "low"


def test_evaluate_mcp_connector_policy_requires_approval_for_high_risk():
    connector = {
        "name": "database-admin",
        "builtin": True,
        "capability_scopes": ["database:read", "database:write"],
        "risk_level": "high",
        "requires_approval": False,
    }

    policy = evaluate_mcp_connector_policy(
        connector,
        allowed_scopes=["database:*"],
    )

    assert policy["allowed"] is False
    assert policy["requires_approval"] is True
    assert "high_risk_requires_approval" in policy["reasons"]
    assert "connector_not_approved" in policy["reasons"]

    allowed_policy = evaluate_mcp_connector_policy(
        connector,
        allowed_scopes=["database:*"],
        allow_high_risk=True,
    )

    assert allowed_policy["allowed"] is True
    assert allowed_policy["requires_approval"] is False
    assert "high_risk_allowed" in allowed_policy["reasons"]


def test_evaluate_mcp_connector_policy_denies_missing_scope():
    policy = evaluate_mcp_connector_policy(
        "web-search",
        allowed_scopes=["web:search"],
    )

    assert policy["allowed"] is False
    assert policy["requires_approval"] is False
    assert policy["missing_scopes"] == ["web:fetch"]
    assert policy["reasons"] == ["scope_missing"]


def test_evaluate_mcp_connector_policy_supports_custom_config_connector():
    connector = {
        "name": "crm-sync",
        "transport": "stdio",
        "command": "python",
        "args": ["crm_server.py"],
        "metadata": {
            "label": "CRM Sync",
            "capability_scopes": ["crm:read", "crm:write", "crm:read"],
            "risk_level": "high",
            "requires_approval": True,
        },
    }

    policy = evaluate_mcp_connector_policy(
        connector,
        allowed_scopes=["crm:*"],
        approved_connector_names=["crm-sync"],
    )

    assert policy["allowed"] is True
    assert policy["requires_approval"] is False
    assert policy["name"] == "crm-sync"
    assert policy["capability_scopes"] == ["crm:read", "crm:write"]
    assert policy["risk_level"] == "high"
    assert policy["approved"] is True
    assert "connector_approved" in policy["reasons"]


def test_select_mcp_connections_enforces_scope_policy(monkeypatch, tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "knowledge-base": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["kb.py"],
                },
                "web-search": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["web.py"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MCP_ALLOWED_SCOPES", "knowledge:*")

    selected = select_mcp_connections(
        project_root=tmp_path,
        config_path=str(config_path),
        enable_mcp_tools=True,
        enabled_server_names=["knowledge-base", "web-search"],
    )

    assert set(selected) == {"knowledge-base"}


def test_select_mcp_connections_allows_high_risk_with_env_approval(monkeypatch, tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "database-admin": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["db.py"],
                    "metadata": {
                        "capability_scopes": ["database:read", "database:write"],
                        "risk_level": "high",
                        "requires_approval": True,
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MCP_ALLOWED_SCOPES", "database:*")
    monkeypatch.setenv("MCP_APPROVED_CONNECTORS", "database-admin")

    selected = select_mcp_connections(
        project_root=tmp_path,
        config_path=str(config_path),
        enable_mcp_tools=True,
        enabled_server_names=["database-admin"],
    )

    assert set(selected) == {"database-admin"}
    assert "metadata" not in selected["database-admin"]


def test_mcp_approval_list_helpers_normalize_add_remove_and_report_sources():
    assert normalize_mcp_approved_connectors(
        " knowledge-base, crm-sync,crm-sync, "
    ) == ["knowledge-base", "crm-sync"]

    added = add_mcp_approved_connector(["knowledge-base"], " crm-sync ")
    assert added == ["knowledge-base", "crm-sync"]
    assert add_mcp_approved_connector(added, "crm-sync") == added
    assert remove_mcp_approved_connector(added, "knowledge-base") == ["crm-sync"]

    payload = list_mcp_approved_connectors(
        "knowledge-base,crm-sync",
        ["crm-sync", "database-admin"],
    )
    assert payload == {
        "approved_connectors": [
            "knowledge-base",
            "crm-sync",
            "database-admin",
        ],
        "env_connectors": ["knowledge-base", "crm-sync"],
        "runtime_connectors": ["crm-sync", "database-admin"],
        "sources": {
            "knowledge-base": ["env"],
            "crm-sync": ["env", "runtime"],
            "database-admin": ["runtime"],
        },
        "total": 3,
    }


def test_select_mcp_connections_allows_high_risk_with_runtime_approval(
    monkeypatch, tmp_path
):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "database-admin": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["db.py"],
                    "metadata": {
                        "capability_scopes": ["database:read", "database:write"],
                        "risk_level": "high",
                        "requires_approval": True,
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("MCP_ALLOWED_SCOPES", "database:*")
    monkeypatch.delenv("MCP_APPROVED_CONNECTORS", raising=False)
    clear_runtime_mcp_approved_connectors()

    denied = select_mcp_connections(
        project_root=tmp_path,
        config_path=str(config_path),
        enable_mcp_tools=True,
        enabled_server_names=["database-admin"],
    )
    assert denied == {}

    try:
        approval_payload = approve_runtime_mcp_connector("database-admin")
        assert approval_payload["connector"]["effective_approved"] is True
        assert current_mcp_approved_connector_names() == ["database-admin"]

        selected = select_mcp_connections(
            project_root=tmp_path,
            config_path=str(config_path),
            enable_mcp_tools=True,
            enabled_server_names=["database-admin"],
        )
        assert set(selected) == {"database-admin"}
    finally:
        clear_runtime_mcp_approved_connectors()


def test_list_mcp_server_catalog_includes_enabled_static_health(tmp_path):
    mcp_dir = tmp_path / "mcp_servers"
    mcp_dir.mkdir()
    (mcp_dir / "knowledge_server.py").write_text("print('knowledge')", encoding="utf-8")
    (mcp_dir / "search_server.py").write_text("print('search')", encoding="utf-8")

    catalog = list_mcp_server_catalog(
        project_root=tmp_path,
        python_command="python",
        enable_mcp_tools=True,
        enabled_server_names=["web-search"],
    )

    by_name = {item["name"]: item for item in catalog}
    assert by_name["web-search"]["enabled"] is True
    assert by_name["web-search"]["healthy"] is True
    assert by_name["web-search"]["status"] == "healthy"
    assert by_name["knowledge-base"]["enabled"] is False
    assert by_name["knowledge-base"]["healthy"] is False
    assert by_name["knowledge-base"]["status"] == "disabled"
    assert "server_not_selected" in by_name["knowledge-base"]["status_reasons"]


def test_list_mcp_server_health_reports_static_configuration_issues(tmp_path):
    missing_script = tmp_path / "missing_server.py"
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "broken": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(missing_script)],
                    "cwd": str(tmp_path),
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    health = list_mcp_server_health(
        project_root=tmp_path,
        config_path=str(config_path),
        enable_mcp_tools=True,
    )

    assert health["summary"] == {
        "total": 1,
        "enabled": 1,
        "configured": 0,
        "healthy": 0,
    }
    server = health["servers"][0]
    assert server["name"] == "broken"
    assert server["enabled"] is True
    assert server["configured"] is False
    assert server["healthy"] is False
    assert server["status"] == "unconfigured"
    assert "entrypoint_missing" in server["status_reasons"]


def test_list_mcp_server_runtime_health_pings_selected_connections():
    clear_mcp_runtime_health_history()

    class FakeTool:
        def __init__(self, name: str):
            self.name = name

    class FakeClient:
        def __init__(self, connections, tool_name_prefix=False):
            self.connections = connections
            self.tool_name_prefix = tool_name_prefix

        async def get_tools(self):
            if "broken" in self.connections:
                raise RuntimeError("handshake failed")
            return [FakeTool("web_search"), FakeTool("knowledge_query")]

    async def run():
        return await list_mcp_server_runtime_health(
            connections={
                "web-search": {"transport": "stdio", "command": "python", "args": []},
                "broken": {"transport": "stdio", "command": "python", "args": []},
            },
            client_factory=FakeClient,
            timeout_seconds=1,
        )

    payload = asyncio.run(run())

    assert payload["status"] == "degraded"
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["healthy"] == 1
    assert payload["summary"]["unhealthy"] == 1
    assert payload["summary"]["tool_count"] == 2
    assert payload["summary"]["status_counts"] == {
        "healthy": 1,
        "unhealthy": 1,
    }
    assert payload["summary"]["unhealthy_connectors"] == ["broken"]
    assert payload["summary"]["alert_count"] == 1
    assert payload["summary"]["alerts"][0]["code"] == "mcp_runtime_unhealthy"
    by_name = {item["name"]: item for item in payload["servers"]}
    assert by_name["web-search"]["status"] == "healthy"
    assert by_name["web-search"]["tools"] == ["knowledge_query", "web_search"]
    assert by_name["broken"]["status"] == "unhealthy"
    assert by_name["broken"]["error"] == "handshake failed"
    assert payload["history_limit"] >= 1
    assert payload["history"][0]["status"] == "degraded"
    assert payload["history"][0]["summary"]["unhealthy_connectors"] == ["broken"]


def test_list_mcp_server_runtime_health_reports_disabled_when_no_connection():
    clear_mcp_runtime_health_history()

    payload = asyncio.run(list_mcp_server_runtime_health(connections={}))

    assert payload["status"] == "disabled"
    assert payload["servers"] == []
    assert payload["summary"]["total"] == 0
    assert payload["summary"]["healthy"] == 0
    assert payload["summary"]["unhealthy"] == 0
    assert payload["summary"]["tool_count"] == 0
    assert payload["summary"]["status_counts"] == {}
    assert payload["summary"]["alerts"] == []
    assert payload["history"][0]["status"] == "disabled"


def test_mcp_runtime_health_history_is_bounded_and_newest_first():
    clear_mcp_runtime_health_history()

    class FakeTool:
        def __init__(self, name: str):
            self.name = name

    class FakeClient:
        def __init__(self, connections, tool_name_prefix=False):
            self.connections = connections

        async def get_tools(self):
            return [FakeTool(f"{next(iter(self.connections))}_tool")]

    async def run(name: str):
        return await list_mcp_server_runtime_health(
            connections={name: {"transport": "stdio", "command": "python", "args": []}},
            client_factory=FakeClient,
            timeout_seconds=1,
        )

    asyncio.run(run("first"))
    payload = asyncio.run(run("second"))

    assert [item["servers"][0]["name"] for item in payload["history"][:2]] == [
        "second",
        "first",
    ]
    assert get_mcp_runtime_health_history(limit=1)[0]["servers"][0]["name"] == "second"


def test_mcp_runtime_health_snapshot_uses_persistence_callback_and_redacts_fields():
    clear_mcp_runtime_health_history()
    persisted: list[dict[str, object]] = []

    snapshot = record_mcp_runtime_health_snapshot(
        {
            "status": "ok",
            "servers": [
                {
                    "name": "private-connector",
                    "status": "healthy",
                    "healthy": True,
                    "tool_count": 1,
                    "tools": ["secret_tool_result"],
                    "duration_ms": 8.5,
                    "error": None,
                    "env": {"API_KEY": "secret"},
                    "args": ["--token", "secret"],
                    "secret": "do-not-store",
                }
            ],
            "summary": {
                "total": 1,
                "healthy": 1,
                "unhealthy": 0,
                "tool_count": 1,
                "status_counts": {"healthy": 1},
                "alert_count": 0,
            },
        },
        recorded_at=123.0,
        history_limit=2,
        history_recorder=lambda item, limit: persisted.append(
            {"item": item, "limit": limit}
        ),
    )

    assert persisted[0]["limit"] == 2
    assert persisted[0]["item"] == snapshot
    server = snapshot["servers"][0]
    assert server == {
        "name": "private-connector",
        "status": "healthy",
        "healthy": True,
        "tool_count": 1,
        "duration_ms": 8.5,
        "error": None,
    }
    snapshot_json = json.dumps(snapshot)
    assert "secret_tool_result" not in snapshot_json
    assert "API_KEY" not in snapshot_json
    assert "--token" not in snapshot_json
    assert "do-not-store" not in snapshot_json


def test_summarize_mcp_runtime_health_reports_alerts_and_slow_connectors():
    summary = summarize_mcp_runtime_health(
        [
            {
                "name": "fast",
                "status": "healthy",
                "healthy": True,
                "duration_ms": 25.0,
                "error": None,
            },
            {
                "name": "slow",
                "status": "healthy",
                "healthy": True,
                "duration_ms": 1500.1234,
                "error": None,
            },
            {
                "name": "stalled",
                "status": "timeout",
                "healthy": False,
                "duration_ms": 2000,
                "error": "runtime_ping_timeout_after_1s",
            },
        ],
        slow_duration_ms=1000,
    )

    assert summary["status_counts"] == {"healthy": 2, "timeout": 1}
    assert summary["unhealthy_connectors"] == ["stalled"]
    assert summary["slow_connectors"] == ["slow", "stalled"]
    assert summary["alert_count"] == 3
    assert [alert["code"] for alert in summary["alerts"]] == [
        "mcp_runtime_slow",
        "mcp_runtime_timeout",
        "mcp_runtime_slow",
    ]
    assert summary["alerts"][1]["severity"] == "critical"


def test_mcp_marketplace_groups_catalog_for_ui():
    marketplace = build_mcp_connector_marketplace(
        [
            {
                "name": "knowledge-base",
                "category": "knowledge",
                "builtin": True,
                "enabled": True,
                "healthy": True,
                "requires_approval": False,
            },
            {
                "name": "crm-sync",
                "category": "crm",
                "builtin": False,
                "enabled": True,
                "healthy": False,
                "requires_approval": True,
            },
        ]
    )

    assert marketplace["summary"] == {
        "total": 2,
        "builtin": 1,
        "custom": 1,
        "enabled": 2,
        "healthy": 1,
        "requires_approval": 1,
        "categories": 2,
    }
    by_category = {item["id"]: item for item in marketplace["categories"]}
    assert by_category["knowledge"]["label"] == "Knowledge"
    assert by_category["crm"]["connectors"] == ["crm-sync"]


def test_mcp_runtime_monitor_payload_summarizes_alerts():
    monitor = build_mcp_runtime_monitor_payload(
        {
            "status": "degraded",
            "summary": {
                "alert_count": 1,
                "unhealthy_connectors": ["broken"],
                "slow_connectors": ["slow"],
                "alerts": [{"code": "mcp_runtime_unhealthy"}],
            },
        }
    )

    assert monitor["status"] == "degraded"
    assert monitor["alert_count"] == 1
    assert monitor["unhealthy_connectors"] == ["broken"]
    assert monitor["slow_connectors"] == ["slow"]
    assert monitor["alerts"] == [{"code": "mcp_runtime_unhealthy"}]
    assert monitor["checked_at"] > 0


def test_mcp_runtime_health_history_store_helpers_are_bounded_and_redacted(tmp_path):
    store = SQLiteAppConfigStore(db_path=str(tmp_path / "config.db"))

    append_mcp_runtime_health_history(
        store,
        {
            "timestamp": 1,
            "status": "ok",
            "summary": {"total": 1, "healthy": 1, "tool_count": 1},
            "servers": [
                {
                    "name": "private",
                    "status": "healthy",
                    "healthy": True,
                    "tool_count": 1,
                    "tools": ["secret_tool"],
                    "env": {"TOKEN": "secret"},
                }
            ],
        },
        limit=2,
    )
    append_mcp_runtime_health_history(
        store,
        {
            "timestamp": 2,
            "status": "degraded",
            "summary": {"total": 1, "unhealthy": 1},
            "servers": [{"name": "broken", "status": "unhealthy"}],
        },
        limit=2,
    )

    history = read_mcp_runtime_health_history(store, limit=2)

    assert [item["status"] for item in history] == ["degraded", "ok"]
    rendered = json.dumps(history, ensure_ascii=False)
    assert "secret_tool" not in rendered
    assert "TOKEN" not in rendered


def test_load_mcp_tool_overrides_filters_expected_names():
    class FakeTool:
        def __init__(self, name: str):
            self.name = name

    class FakeClient:
        def __init__(self, connections, tool_name_prefix=False):
            self.connections = connections
            self.tool_name_prefix = tool_name_prefix

        async def get_tools(self):
            return [FakeTool("web_search"), FakeTool("custom_tool")]

    async def run():
        return await load_mcp_tool_overrides(
            connections={"web-search": {"transport": "stdio", "command": "python", "args": []}},
            expected_tool_names={"web_search"},
            client_factory=FakeClient,
        )

    tools = asyncio.run(run())

    assert set(tools) == {"web_search"}


def test_load_mcp_tool_overrides_supports_real_stdio_server(tmp_path):
    server_script = tmp_path / "fake_mcp_server.py"
    server_script.write_text(
        """
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fake")

@mcp.tool()
async def web_search(search_query: str) -> str:
    return f"echo:{search_query}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
""".strip(),
        encoding="utf-8",
    )

    async def run():
        tools = await load_mcp_tool_overrides(
            connections={
                "fake": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(server_script)],
                    "cwd": str(tmp_path),
                    "encoding": "utf-8",
                }
            },
            expected_tool_names={"web_search"},
        )
        tool = tools["web_search"]
        assert "search_query" in tool.args
        assert await tool.ainvoke({"search_query": "hello"}) == "echo:hello"

    asyncio.run(run())
