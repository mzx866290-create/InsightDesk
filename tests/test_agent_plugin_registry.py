import asyncio
import json

from backend.agent.registry import (
    create_default_agent_registry,
    install_agent_plugin_manifest_payload,
    list_agent_catalog,
    list_agent_plugin_marketplace,
    load_agent_plugin_manifest_report,
    load_agent_plugin_manifests,
    uninstall_agent_plugin_manifest_payload,
)


def test_registry_loads_declarative_agent_plugin_manifest(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "market-research.json").write_text(
        json.dumps(
            {
                "name": "market_research",
                "version": "1.0.0",
                "description": "Market research workflow plugin.",
                "capabilities": ["market_research", "competitive_scan"],
                "output_prefix": "Market research plugin completed",
                "risk_level": "high",
                "requires_approval": True,
                "approval_reason": "External market data export.",
                "entrypoint": "should.not.be.imported",
                "metadata": {"tier": "plugin", "unsafe": {"ignored": True}},
            }
        ),
        encoding="utf-8",
    )

    registry = create_default_agent_registry(plugin_dirs=[plugin_dir])
    agent = registry.get("market_research")
    result = asyncio.run(
        agent.execute(
            {
                "id": "task-plugin-1",
                "type": "market_research",
                "description": "scan competitors",
            },
            {"workspace_id": "workspace-1"},
        )
    )

    assert registry.find_for_task("competitive_scan") is agent
    assert result["output"] == "Market research plugin completed: scan competitors"
    assert result["metadata"]["plugin"] is True
    assert result["metadata"]["source"] == "plugin_manifest"
    assert result["metadata"]["version"] == "1.0.0"
    assert result["metadata"]["risk_level"] == "high"
    assert result["metadata"]["requires_approval"] is True
    assert result["metadata"]["approval_reason"] == "External market data export."
    assert "entrypoint" not in result["metadata"]
    assert "unsafe" not in result["metadata"]


def test_registry_loads_workflow_agent_plugin_manifest(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "customer-health.json").write_text(
        json.dumps(
            {
                "name": "customer_health_workflow",
                "version": "1.0.0",
                "runtime": "workflow_manifest",
                "description": "Customer health review workflow plugin.",
                "capabilities": ["customer_health", "account_review"],
                "output_prefix": "Customer health workflow completed",
                "risk_level": "medium",
                "workflow": [
                    {
                        "id": "signals",
                        "title": "Collect signals",
                        "prompt": "Review signals for {description} in {context_keys}.",
                        "artifact_type": "analysis_note",
                    },
                    {
                        "id": "actions",
                        "title": "Recommend actions",
                        "prompt": "Create actions for {task_type}.",
                        "artifact_type": "action_plan",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    registry = create_default_agent_registry(plugin_dirs=[plugin_dir])
    agent = registry.get("customer_health_workflow")
    result = asyncio.run(
        agent.execute(
            {
                "id": "task-plugin-2",
                "type": "customer_health",
                "description": "ACME renewal",
            },
            {"account": {"name": "ACME"}, "workspace_id": "workspace-1"},
        )
    )

    assert registry.find_for_task("account_review") is agent
    assert result["metadata"]["runtime"] == "workflow_manifest"
    assert result["metadata"]["workflow_step_count"] == 2
    assert "Collect signals: Review signals for ACME renewal in account, workspace_id." in result["output"]
    assert result["artifacts"] == [
        {
            "type": "analysis_note",
            "title": "Collect signals",
            "content": "Review signals for ACME renewal in account, workspace_id.",
        },
        {
            "type": "action_plan",
            "title": "Recommend actions",
            "content": "Create actions for customer_health.",
        },
    ]


def test_agent_plugin_loader_skips_disabled_invalid_and_duplicate_manifests(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "a.json").write_text(
        json.dumps(
            {
                "name": "duplicate_plugin",
                "description": "First valid plugin.",
                "capabilities": ["first"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "b.json").write_text(
        json.dumps(
            {
                "name": "duplicate_plugin",
                "description": "Duplicate valid plugin.",
                "capabilities": ["second"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "disabled.json").write_text(
        json.dumps(
            {
                "name": "disabled_plugin",
                "enabled": False,
                "description": "Disabled plugin.",
                "capabilities": ["disabled"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "invalid.json").write_text(
        json.dumps({"name": "bad plugin", "capabilities": []}),
        encoding="utf-8",
    )

    report = load_agent_plugin_manifest_report([plugin_dir])
    agents = load_agent_plugin_manifests([plugin_dir])

    assert [agent.name for agent in agents] == ["duplicate_plugin"]
    assert agents[0].capabilities == ["first"]
    assert [agent.name for agent in report.agents] == ["duplicate_plugin"]
    assert report.scanned_count == 4
    assert [issue.code for issue in report.issues] == [
        "duplicate_name",
        "invalid_manifest",
    ]


def test_agent_catalog_counts_builtin_and_plugin_agents(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "support.json").write_text(
        json.dumps(
            {
                "name": "support_triage",
                "description": "Support triage plugin.",
                "capabilities": ["support_triage"],
            }
        ),
        encoding="utf-8",
    )

    payload = list_agent_catalog(plugin_dirs=[plugin_dir])

    assert payload["summary"] == {"total": 8, "builtin": 7, "plugin": 1}
    assert payload["plugin_manifests"] == {
        "enabled": True,
        "directory_count": 1,
        "scanned_count": 1,
        "loaded_count": 1,
        "issue_count": 0,
        "issues": [],
    }
    assert payload["marketplace"]["summary"]["installed"] >= 1
    assert any(
        template["name"] == "support_triage" and template["installed"]
        for template in payload["marketplace"]["templates"]
    )
    assert [agent["name"] for agent in payload["agents"]][-2:] == [
        "support_triage",
        "general",
    ]


def test_agent_plugin_loader_rejects_invalid_risk_level(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "risky.json").write_text(
        json.dumps(
            {
                "name": "risky_plugin",
                "description": "Invalid risk plugin.",
                "capabilities": ["risky"],
                "risk_level": "dangerous",
            }
        ),
        encoding="utf-8",
    )

    report = load_agent_plugin_manifest_report([plugin_dir])

    assert report.agents == []
    assert report.scanned_count == 1
    assert report.issues[0].code == "invalid_manifest"
    assert "risk_level" in report.issues[0].message


def test_install_agent_plugin_manifest_persists_sanitized_manifest_without_execution(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"

    payload = install_agent_plugin_manifest_payload(
        {
            "name": "sales_enablement",
            "version": "1.2.0",
            "description": "Sales enablement workflow plugin.",
            "capabilities": ["sales_enablement", "sales_brief"],
            "output_prefix": "Sales enablement plugin completed",
            "risk_level": "medium",
            "requires_approval": True,
            "approval_reason": "May export customer context.",
            "entrypoint": "should.not.execute",
            "metadata": {
                "owner": "sales",
                "unsafe": {"ignored": True},
                "source": "spoofed",
            },
        },
        plugin_dirs=[plugin_dir],
    )

    manifest_path = plugin_dir / "sales_enablement.json"
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["installed"]["name"] == "sales_enablement"
    assert payload["installed"]["executed_entrypoint"] is False
    assert payload["summary"]["plugin"] == 1
    assert payload["agents"][-2]["name"] == "sales_enablement"
    assert saved == {
        "approval_reason": "May export customer context.",
        "capabilities": ["sales_enablement", "sales_brief"],
        "description": "Sales enablement workflow plugin.",
        "enabled": True,
        "metadata": {"owner": "sales"},
        "name": "sales_enablement",
        "output_prefix": "Sales enablement plugin completed",
        "requires_approval": True,
        "risk_level": "medium",
        "version": "1.2.0",
    }
    assert "entrypoint" not in saved


def test_install_agent_plugin_manifest_persists_sanitized_workflow_manifest(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"

    payload = install_agent_plugin_manifest_payload(
        {
            "name": "renewal_workflow",
            "version": "1.0.0",
            "runtime": "workflow_manifest",
            "description": "Renewal workflow plugin.",
            "capabilities": ["renewal_review"],
            "output_prefix": "Renewal workflow completed",
            "risk_level": "medium",
            "workflow": [
                {
                    "id": "summary",
                    "title": "Summarize account",
                    "prompt": "Summarize renewal context for {description}.",
                    "artifact_type": "brief",
                    "unsafe": {"ignored": True},
                }
            ],
            "entrypoint": "should.not.execute",
        },
        plugin_dirs=[plugin_dir],
    )

    saved = json.loads((plugin_dir / "renewal_workflow.json").read_text(encoding="utf-8"))

    assert payload["installed"]["name"] == "renewal_workflow"
    assert payload["installed"]["executed_entrypoint"] is False
    assert saved == {
        "capabilities": ["renewal_review"],
        "description": "Renewal workflow plugin.",
        "enabled": True,
        "name": "renewal_workflow",
        "output_prefix": "Renewal workflow completed",
        "risk_level": "medium",
        "runtime": "workflow_manifest",
        "version": "1.0.0",
        "workflow": [
            {
                "artifact_type": "brief",
                "id": "summary",
                "prompt": "Summarize renewal context for {description}.",
                "title": "Summarize account",
            }
        ],
    }


def test_install_agent_plugin_manifest_rejects_builtin_name(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"

    try:
        install_agent_plugin_manifest_payload(
            {
                "name": "research",
                "description": "Conflicting plugin.",
                "capabilities": ["research"],
            },
            plugin_dirs=[plugin_dir],
        )
    except ValueError as exc:
        assert "conflicts with built-in agent" in str(exc)
    else:
        raise AssertionError("Expected built-in name conflict")


def test_uninstall_agent_plugin_manifest_removes_persisted_file(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    install_agent_plugin_manifest_payload(
        {
            "name": "sales_enablement",
            "description": "Sales enablement workflow plugin.",
            "capabilities": ["sales_enablement"],
            "risk_level": "medium",
        },
        plugin_dirs=[plugin_dir],
    )

    payload = uninstall_agent_plugin_manifest_payload(
        "sales_enablement",
        plugin_dirs=[plugin_dir],
    )

    assert payload["uninstalled"]["name"] == "sales_enablement"
    assert payload["uninstalled"]["deleted_manifest"] is True
    assert not (plugin_dir / "sales_enablement.json").exists()
    assert payload["summary"]["plugin"] == 0


def test_uninstall_agent_plugin_manifest_rejects_builtin_name(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"

    try:
        uninstall_agent_plugin_manifest_payload(
            "research",
            plugin_dirs=[plugin_dir],
        )
    except ValueError as exc:
        assert "conflicts with built-in agent" in str(exc)
    else:
        raise AssertionError("Expected built-in name conflict")


def test_uninstall_agent_plugin_manifest_rejects_invalid_or_missing_name(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"

    for name, expected in [
        ("bad plugin", "Agent plugin manifest name"),
        ("missing_plugin", "not found"),
    ]:
        try:
            uninstall_agent_plugin_manifest_payload(
                name,
                plugin_dirs=[plugin_dir],
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"Expected uninstall failure for {name}")


def test_agent_plugin_marketplace_lists_templates_and_marks_installed(tmp_path):
    plugin_dir = tmp_path / "agent_plugins"
    plugin_dir.mkdir()
    (plugin_dir / "support_triage.json").write_text(
        json.dumps(
            {
                "name": "support_triage",
                "description": "Installed support plugin.",
                "capabilities": ["support_triage"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "custom.example.json").write_text(
        json.dumps(
            {
                "enabled": False,
                "name": "sales_enablement",
                "description": "Sales template plugin.",
                "capabilities": ["sales_enablement"],
                "metadata": {"category": "sales"},
            }
        ),
        encoding="utf-8",
    )

    marketplace = list_agent_plugin_marketplace(plugin_dirs=[plugin_dir])
    templates = {template["name"]: template for template in marketplace["templates"]}

    assert marketplace["summary"]["total"] >= 5
    assert templates["support_triage"]["installed"] is True
    assert templates["support_triage"]["manifest"]["enabled"] is True
    assert templates["sales_enablement"]["installed"] is False
    assert templates["sales_enablement"]["category"] == "sales"
    assert templates["sales_enablement"]["manifest"]["enabled"] is True
