from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.registry import (
    install_agent_plugin_manifest_payload,
    uninstall_agent_plugin_manifest_payload,
)
from backend.routes.agent_catalog_routes import build_agent_catalog_router
from backend.schemas.api_models import AgentCatalogResponse


def test_agent_catalog_endpoint_returns_stable_catalog_payload():
    app = FastAPI()
    audit_events: list[tuple[str, str]] = []

    app.include_router(
        build_agent_catalog_router(
            agent_catalog_response_model=AgentCatalogResponse,
            list_agent_catalog=lambda: {
                "agents": [
                    {
                        "name": "research",
                        "description": "Research agent",
                        "capabilities": ["research"],
                        "metadata": {},
                    },
                    {
                        "name": "support_triage",
                        "description": "Support plugin",
                        "capabilities": ["support_triage"],
                        "metadata": {"plugin": True, "source": "plugin_manifest"},
                    },
                ],
                "summary": {"total": 2, "builtin": 1, "plugin": 1},
                "plugin_manifests": {"enabled": True, "directory_count": 1},
                "marketplace": {
                    "templates": [
                        {
                            "name": "support_triage",
                            "description": "Support template",
                            "capabilities": ["support_triage"],
                            "category": "operations",
                            "risk_level": "medium",
                            "requires_approval": True,
                            "approval_reason": "Support routing",
                            "source": "builtin",
                            "installed": True,
                            "template": True,
                            "manifest": {
                                "name": "support_triage",
                                "description": "Support template",
                                "capabilities": ["support_triage"],
                            },
                        }
                    ],
                    "summary": {
                        "total": 1,
                        "installed": 1,
                        "available": 0,
                        "categories": 1,
                        "issue_count": 0,
                    },
                    "issues": [],
                },
            },
            install_agent_plugin_manifest_payload=lambda manifest: {
                "agents": [],
                "summary": {"total": 0, "builtin": 0, "plugin": 0},
                "plugin_manifests": {"enabled": True, "directory_count": 1},
                "installed": {
                    "name": str(manifest.get("name") or ""),
                    "manifest_path": "unused",
                    "executed_entrypoint": False,
                },
            },
            uninstall_agent_plugin_manifest_payload=lambda name: {
                "agents": [],
                "summary": {"total": 0, "builtin": 0, "plugin": 0},
                "plugin_manifests": {"enabled": True, "directory_count": 1},
                "uninstalled": {
                    "name": name,
                    "manifest_path": "unused",
                    "deleted_manifest": True,
                    "existed": True,
                },
            },
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda action, request, details="": audit_events.append(
                (action, details)
            ),
        )
    )

    response = TestClient(app).get("/api/agents/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {"total": 2, "builtin": 1, "plugin": 1}
    assert payload["agents"][1]["metadata"]["source"] == "plugin_manifest"
    assert payload["marketplace"]["templates"][0]["installed"] is True
    assert audit_events == [("get_agent_catalog", "total=2 plugin=1")]


def test_agent_plugin_install_endpoint_persists_manifest_without_execution(tmp_path):
    app = FastAPI()
    audit_events: list[tuple[str, str]] = []
    plugin_dir = tmp_path / "agent_plugins"

    app.include_router(
        build_agent_catalog_router(
            agent_catalog_response_model=AgentCatalogResponse,
            list_agent_catalog=lambda: {"agents": [], "summary": {}, "plugin_manifests": {}},
            install_agent_plugin_manifest_payload=lambda manifest: install_agent_plugin_manifest_payload(
                manifest,
                plugin_dirs=[plugin_dir],
            ),
            uninstall_agent_plugin_manifest_payload=lambda name: uninstall_agent_plugin_manifest_payload(
                name,
                plugin_dirs=[plugin_dir],
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda action, request, details="": audit_events.append(
                (action, details)
            ),
        )
    )

    response = TestClient(app).post(
        "/api/agents/plugins/install",
        json={
            "manifest": {
                "name": "support_triage",
                "description": "Support triage plugin.",
                "capabilities": ["support_triage"],
                "risk_level": "low",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["installed"]["name"] == "support_triage"
    assert payload["installed"]["executed_entrypoint"] is False
    assert (plugin_dir / "support_triage.json").is_file()
    assert audit_events == [
        ("install_agent_plugin_manifest", "name=support_triage total=8")
    ]


def test_agent_plugin_uninstall_endpoint_removes_manifest_without_execution(tmp_path):
    app = FastAPI()
    audit_events: list[tuple[str, str]] = []
    plugin_dir = tmp_path / "agent_plugins"
    install_agent_plugin_manifest_payload(
        {
            "name": "support_triage",
            "description": "Support triage plugin.",
            "capabilities": ["support_triage"],
        },
        plugin_dirs=[plugin_dir],
    )

    app.include_router(
        build_agent_catalog_router(
            agent_catalog_response_model=AgentCatalogResponse,
            list_agent_catalog=lambda: {"agents": [], "summary": {}, "plugin_manifests": {}},
            install_agent_plugin_manifest_payload=lambda manifest: install_agent_plugin_manifest_payload(
                manifest,
                plugin_dirs=[plugin_dir],
            ),
            uninstall_agent_plugin_manifest_payload=lambda name: uninstall_agent_plugin_manifest_payload(
                name,
                plugin_dirs=[plugin_dir],
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda action, request, details="": audit_events.append(
                (action, details)
            ),
        )
    )

    response = TestClient(app).delete("/api/agents/plugins/support_triage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["uninstalled"]["name"] == "support_triage"
    assert payload["uninstalled"]["deleted_manifest"] is True
    assert not (plugin_dir / "support_triage.json").exists()
    assert audit_events == [
        ("uninstall_agent_plugin_manifest", "name=support_triage total=7")
    ]


def test_agent_plugin_install_endpoint_rejects_invalid_manifest(tmp_path):
    app = FastAPI()

    app.include_router(
        build_agent_catalog_router(
            agent_catalog_response_model=AgentCatalogResponse,
            list_agent_catalog=lambda: {"agents": [], "summary": {}, "plugin_manifests": {}},
            install_agent_plugin_manifest_payload=lambda manifest: install_agent_plugin_manifest_payload(
                manifest,
                plugin_dirs=[tmp_path / "agent_plugins"],
            ),
            uninstall_agent_plugin_manifest_payload=lambda name: uninstall_agent_plugin_manifest_payload(
                name,
                plugin_dirs=[tmp_path / "agent_plugins"],
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda *args, **kwargs: None,
        )
    )

    response = TestClient(app).post(
        "/api/agents/plugins/install",
        json={"manifest": {"name": "bad plugin", "capabilities": []}},
    )

    assert response.status_code == 400
    assert "Agent plugin manifest name" in response.json()["detail"]


def test_agent_plugin_uninstall_endpoint_rejects_missing_manifest(tmp_path):
    app = FastAPI()

    app.include_router(
        build_agent_catalog_router(
            agent_catalog_response_model=AgentCatalogResponse,
            list_agent_catalog=lambda: {"agents": [], "summary": {}, "plugin_manifests": {}},
            install_agent_plugin_manifest_payload=lambda manifest: install_agent_plugin_manifest_payload(
                manifest,
                plugin_dirs=[tmp_path / "agent_plugins"],
            ),
            uninstall_agent_plugin_manifest_payload=lambda name: uninstall_agent_plugin_manifest_payload(
                name,
                plugin_dirs=[tmp_path / "agent_plugins"],
            ),
            require_remote_viewer=lambda request: {"role": "viewer"},
            require_remote_admin=lambda request: {"role": "admin"},
            audit_security_event=lambda *args, **kwargs: None,
        )
    )

    response = TestClient(app).delete("/api/agents/plugins/missing_plugin")

    assert response.status_code == 400
    assert "not found" in response.json()["detail"]
