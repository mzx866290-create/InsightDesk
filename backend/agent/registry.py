"""Agent registration and discovery for the multi-agent runtime."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from backend.agent.agents.data_analysis import DataAnalysisAgent
from backend.agent.agents.integrator import IntegratorAgent, IntegratorAgentConfig
from backend.agent.agents.model_compare import ModelCompareAgent, ModelCompareAgentConfig
from backend.agent.agents.reviewer import ReviewAgent
from backend.agent.agents.researcher import DeepResearchAgent, ResearchAgentConfig
from backend.agent.agents.writer import WritingAgent
from backend.agent.protocols import AgentProtocol, AgentResult, AgentTask

AGENT_PLUGIN_DIRS_ENV = "AGENT_PLUGIN_MANIFEST_DIRS"
AGENT_PLUGIN_MARKETPLACE_DIRS_ENV = "AGENT_PLUGIN_MARKETPLACE_DIRS"
AGENT_PLUGIN_ENABLED_ENV = "AGENT_PLUGIN_MANIFESTS_ENABLED"
_AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_AGENT_RISK_LEVELS = {"low", "medium", "high", "critical"}
_AGENT_MANIFEST_STATIC_RUNTIMES = {"", "static", "static_manifest"}
_AGENT_MANIFEST_WORKFLOW_RUNTIMES = {"workflow", "workflow_manifest"}
_AGENT_MANIFEST_ALLOWED_RUNTIMES = (
    _AGENT_MANIFEST_STATIC_RUNTIMES | _AGENT_MANIFEST_WORKFLOW_RUNTIMES
)
_AGENT_WORKFLOW_STEP_LIMIT = 12
_PLUGIN_METADATA_RESERVED_KEYS = {
    "approval_reason",
    "plugin",
    "requires_approval",
    "risk",
    "risk_level",
    "runtime",
    "source",
    "version",
}
_BUILTIN_AGENT_PLUGIN_MARKETPLACE_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "enabled": True,
        "name": "market_research",
        "version": "1.0.0",
        "description": "Static Agent plugin for market and competitor research workflows.",
        "capabilities": ["market_research", "competitive_scan"],
        "output_prefix": "Market research plugin completed",
        "risk_level": "medium",
        "requires_approval": False,
        "metadata": {"category": "research", "owner": "builtin"},
    },
    {
        "enabled": True,
        "name": "support_triage",
        "version": "1.0.0",
        "description": "Static Agent plugin for classifying support requests and routing queues.",
        "capabilities": ["support_triage", "customer_support"],
        "output_prefix": "Support triage plugin completed",
        "risk_level": "medium",
        "requires_approval": True,
        "approval_reason": "May inspect customer support context before routing tasks.",
        "metadata": {"category": "operations", "owner": "builtin"},
    },
    {
        "enabled": True,
        "name": "data_quality_auditor",
        "version": "1.0.0",
        "description": "Static Agent plugin for dataset quality checks and anomaly review.",
        "capabilities": ["data_quality", "anomaly_review"],
        "output_prefix": "Data quality audit plugin completed",
        "risk_level": "low",
        "requires_approval": False,
        "metadata": {"category": "analysis", "owner": "builtin"},
    },
    {
        "enabled": True,
        "name": "release_notes_writer",
        "version": "1.0.0",
        "description": "Static Agent plugin for turning change summaries into release notes.",
        "capabilities": ["release_notes", "changelog"],
        "output_prefix": "Release notes plugin completed",
        "risk_level": "low",
        "requires_approval": False,
        "metadata": {"category": "writing", "owner": "builtin"},
    },
    {
        "enabled": True,
        "name": "customer_health_workflow",
        "version": "1.0.0",
        "runtime": "workflow_manifest",
        "description": "Dynamic workflow Agent plugin for customer health reviews.",
        "capabilities": ["customer_health", "account_review"],
        "output_prefix": "Customer health workflow completed",
        "risk_level": "medium",
        "requires_approval": True,
        "approval_reason": "May combine account, support, and renewal context.",
        "workflow": [
            {
                "id": "signals",
                "title": "Collect health signals",
                "prompt": "Review recent usage, support, and renewal signals for {description}.",
                "artifact_type": "analysis_note",
            },
            {
                "id": "risks",
                "title": "Identify risks",
                "prompt": "List retention risks, expansion blockers, and missing context.",
                "artifact_type": "risk_summary",
            },
            {
                "id": "actions",
                "title": "Recommend actions",
                "prompt": "Create next-best actions for the account team.",
                "artifact_type": "action_plan",
            },
        ],
        "metadata": {"category": "operations", "owner": "builtin"},
    },
)


class AgentRegistry:
    """In-memory registry used by the orchestrator to discover specialist Agents."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentProtocol] = {}

    def register(self, agent: AgentProtocol, *, replace: bool = False) -> None:
        name = str(agent.name or "").strip()
        if not name:
            raise ValueError("Agent name cannot be empty")
        if name in self._agents and not replace:
            raise ValueError(f"Agent already registered: {name}")
        self._agents[name] = agent

    def get(self, name: str) -> AgentProtocol:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise KeyError(f"Agent not registered: {name}") from exc

    def find_for_task(self, task_type: str) -> AgentProtocol | None:
        for agent in self._agents.values():
            if agent.can_handle(task_type):
                return agent
        return self._agents.get("general")

    def list_agents(self) -> list[AgentProtocol]:
        return list(self._agents.values())

    def describe_agents(self) -> list[dict[str, Any]]:
        """Return a stable, serializable catalog of registered Agents."""
        return [self._describe_agent(agent) for agent in self._agents.values()]

    @staticmethod
    def _describe_agent(agent: AgentProtocol) -> dict[str, Any]:
        raw_capabilities = getattr(agent, "capabilities", ())
        if isinstance(raw_capabilities, str):
            raw_capabilities = (raw_capabilities,)

        return {
            "name": str(getattr(agent, "name", "") or "").strip(),
            "description": str(getattr(agent, "description", "") or "").strip(),
            "capabilities": [str(capability) for capability in raw_capabilities],
            "metadata": AgentRegistry._agent_metadata(agent),
        }

    @staticmethod
    def _agent_metadata(agent: AgentProtocol) -> dict[str, Any]:
        raw_metadata = getattr(agent, "metadata", None)
        if not isinstance(raw_metadata, dict):
            config = getattr(agent, "config", None)
            raw_metadata = getattr(config, "metadata", None)
        return dict(raw_metadata) if isinstance(raw_metadata, dict) else {}


@dataclass(slots=True)
class StaticAgent:
    """Default deterministic Agent used until a specialist gains runtime logic."""

    name: str
    description: str
    capabilities: list[str]
    output_prefix: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(
        self,
        task: AgentTask,
        context: dict[str, Any],
    ) -> AgentResult:
        description = str(task.get("description") or task.get("input") or "").strip()
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": f"{self.output_prefix}: {description}" if description else self.output_prefix,
            "artifacts": [],
            "sources": [],
            "metadata": {**self.metadata, "context_keys": sorted(context.keys())},
        }


@dataclass(slots=True)
class WorkflowManifestAgent:
    """Declarative Agent that executes a safe manifest-defined workflow."""

    name: str
    description: str
    capabilities: list[str]
    output_prefix: str
    workflow: list[dict[str, str]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(
        self,
        task: AgentTask,
        context: dict[str, Any],
    ) -> AgentResult:
        description = str(task.get("description") or task.get("input") or "").strip()
        rendered_steps: list[dict[str, str]] = []
        for index, step in enumerate(self.workflow, start=1):
            rendered_steps.append(
                {
                    "id": step["id"],
                    "title": step["title"],
                    "prompt": _render_workflow_prompt(
                        step["prompt"],
                        task=task,
                        context=context,
                    ),
                    "artifact_type": step["artifact_type"],
                    "order": str(index),
                }
            )
        step_lines = [
            f"{step['order']}. {step['title']}: {step['prompt']}"
            for step in rendered_steps
        ]
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": "\n".join(
                [
                    f"{self.output_prefix}: {description}"
                    if description
                    else self.output_prefix,
                    *step_lines,
                ]
            ),
            "artifacts": [
                {
                    "type": step["artifact_type"],
                    "title": step["title"],
                    "content": step["prompt"],
                }
                for step in rendered_steps
            ],
            "sources": [],
            "metadata": {
                **self.metadata,
                "workflow_step_count": len(rendered_steps),
                "context_keys": sorted(context.keys()),
            },
        }


@dataclass(slots=True)
class AgentPluginManifestIssue:
    """Safe, serializable diagnostics for manifests that cannot be loaded."""

    file: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "file": self.file,
            "code": self.code,
            "message": self.message,
        }


@dataclass(slots=True)
class AgentPluginManifestLoadReport:
    """Manifest load result used by the catalog without executing plugin code."""

    agents: list[AgentProtocol] = field(default_factory=list)
    issues: list[AgentPluginManifestIssue] = field(default_factory=list)
    directories: list[Path] = field(default_factory=list)
    scanned_count: int = 0


def create_default_agent_registry(
    *,
    research_agent: AgentProtocol | None = None,
    data_analysis_agent: AgentProtocol | None = None,
    writing_agent: AgentProtocol | None = None,
    review_agent: AgentProtocol | None = None,
    integrator_agent: AgentProtocol | None = None,
    model_compare_agent: AgentProtocol | None = None,
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
    include_plugin_manifests: bool = True,
) -> AgentRegistry:
    """Create the baseline registry described in the implementation plan."""
    registry = AgentRegistry()
    for agent in (
        research_agent
        or StaticAgent(
            name="research",
            description="Research Agent for search, evidence collection, and deep research tasks.",
            capabilities=["research", "deep_research", "web_search"],
            output_prefix="Research Agent completed evidence collection",
        ),
        data_analysis_agent or DataAnalysisAgent(),
        writing_agent or WritingAgent(),
        review_agent or ReviewAgent(),
        integrator_agent or IntegratorAgent(),
        model_compare_agent or ModelCompareAgent(),
    ):
        registry.register(agent)

    if include_plugin_manifests:
        register_agent_plugin_manifests(registry, plugin_dirs=plugin_dirs)

    registry.register(
        StaticAgent(
            name="general",
            description="General fallback Agent for tasks without a specialist.",
            capabilities=["general"],
            output_prefix="General Agent completed task handling",
        ),
    )
    return registry


def create_runtime_agent_registry(
    *,
    llm: Any | None = None,
    research_config: ResearchAgentConfig | None = None,
    model_compare_config: ModelCompareAgentConfig | None = None,
    integrator_connectors: tuple[Any, ...] | list[Any] | None = None,
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
    include_plugin_manifests: bool = True,
) -> AgentRegistry:
    """Create a registry with runtime-backed specialist Agents when possible."""
    integrator_config = IntegratorAgentConfig(
        connectors=tuple(integrator_connectors or ())
    )
    return create_default_agent_registry(
        research_agent=DeepResearchAgent(llm=llm, config=research_config),
        data_analysis_agent=DataAnalysisAgent(llm=llm),
        writing_agent=WritingAgent(llm=llm),
        review_agent=ReviewAgent(llm=llm),
        integrator_agent=IntegratorAgent(config=integrator_config),
        model_compare_agent=ModelCompareAgent(config=model_compare_config),
        plugin_dirs=plugin_dirs,
        include_plugin_manifests=include_plugin_manifests,
    )


def agent_plugin_manifests_enabled() -> bool:
    raw_value = str(os.getenv(AGENT_PLUGIN_ENABLED_ENV, "true") or "").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def default_agent_plugin_dirs() -> list[Path]:
    """Return declarative plugin manifest directories without requiring them to exist."""

    root = Path(__file__).resolve().parents[2]
    configured = [
        item.strip()
        for item in str(os.getenv(AGENT_PLUGIN_DIRS_ENV, "") or "").split(os.pathsep)
        if item.strip()
    ]
    candidates = configured or [str(root / "config" / "agent_plugins")]
    return [Path(item).expanduser() for item in candidates]


def default_agent_plugin_marketplace_dirs() -> list[Path]:
    """Return optional marketplace template directories without requiring them to exist."""

    root = Path(__file__).resolve().parents[2]
    configured = [
        item.strip()
        for item in str(os.getenv(AGENT_PLUGIN_MARKETPLACE_DIRS_ENV, "") or "").split(os.pathsep)
        if item.strip()
    ]
    candidates = configured or [str(root / "config" / "agent_plugin_marketplace")]
    return [Path(item).expanduser() for item in candidates]


def _normalize_manifest_strings(raw_value: Any, *, field_name: str) -> list[str]:
    if not isinstance(raw_value, list):
        raise ValueError(f"Agent plugin manifest field '{field_name}' must be a list")
    values = [str(item).strip() for item in raw_value if str(item).strip()]
    if not values:
        raise ValueError(f"Agent plugin manifest field '{field_name}' cannot be empty")
    return values


def _safe_manifest_metadata(raw_metadata: Any) -> dict[str, Any]:
    if not isinstance(raw_metadata, dict):
        return {}
    allowed: dict[str, Any] = {}
    for key, value in raw_metadata.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            allowed[normalized_key] = value
        elif isinstance(value, list):
            allowed[normalized_key] = [
                item for item in value if isinstance(item, (str, int, float, bool))
            ]
    return allowed


def _normalize_manifest_risk_level(value: Any) -> str:
    risk_level = str(value or "").strip().lower()
    if not risk_level:
        return ""
    if risk_level not in _AGENT_RISK_LEVELS:
        raise ValueError(
            "Agent plugin manifest risk_level must be one of: "
            "low, medium, high, critical"
        )
    return risk_level


def _normalize_manifest_runtime(value: Any) -> str:
    runtime = str(value or "").strip().lower()
    if runtime not in _AGENT_MANIFEST_ALLOWED_RUNTIMES:
        raise ValueError(
            "Agent plugin manifest runtime must be one of: "
            "static_manifest or workflow_manifest"
        )
    return "workflow_manifest" if runtime in _AGENT_MANIFEST_WORKFLOW_RUNTIMES else "static_manifest"


def _normalize_workflow_step_id(value: Any, *, index: int) -> str:
    raw_id = str(value or "").strip()
    if not raw_id:
        return f"step_{index}"
    if not _AGENT_NAME_PATTERN.fullmatch(raw_id):
        raise ValueError(
            "Agent plugin workflow step id must be 1-64 characters and use only "
            "letters, numbers, dots, underscores, or hyphens"
        )
    return raw_id


def _normalize_manifest_workflow(raw_workflow: Any) -> list[dict[str, str]]:
    if not isinstance(raw_workflow, list):
        raise ValueError("Agent plugin manifest workflow must be a list")
    if not raw_workflow:
        raise ValueError("Agent plugin manifest workflow cannot be empty")
    if len(raw_workflow) > _AGENT_WORKFLOW_STEP_LIMIT:
        raise ValueError(
            f"Agent plugin manifest workflow cannot exceed {_AGENT_WORKFLOW_STEP_LIMIT} steps"
        )

    steps: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, raw_step in enumerate(raw_workflow, start=1):
        if not isinstance(raw_step, dict):
            raise ValueError("Agent plugin workflow step must be an object")
        step_id = _normalize_workflow_step_id(raw_step.get("id"), index=index)
        if step_id in seen_ids:
            raise ValueError(f"Duplicate Agent plugin workflow step id: {step_id}")
        seen_ids.add(step_id)
        title = str(raw_step.get("title") or raw_step.get("name") or "").strip()
        if not title:
            raise ValueError("Agent plugin workflow step title cannot be empty")
        prompt = str(raw_step.get("prompt") or raw_step.get("instruction") or "").strip()
        if not prompt:
            raise ValueError("Agent plugin workflow step prompt cannot be empty")
        artifact_type = str(raw_step.get("artifact_type") or "text").strip() or "text"
        steps.append(
            {
                "id": step_id,
                "title": title[:120],
                "prompt": prompt[:2000],
                "artifact_type": artifact_type[:64],
            }
        )
    return steps


def _render_workflow_prompt(
    prompt: str,
    *,
    task: AgentTask,
    context: dict[str, Any],
) -> str:
    values = {
        "description": str(task.get("description") or ""),
        "input": str(task.get("input") or ""),
        "task_type": str(task.get("type") or ""),
        "task_id": str(task.get("id") or ""),
        "context_keys": ", ".join(sorted(context.keys())),
    }
    rendered = str(prompt)
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _agent_from_manifest(payload: dict[str, Any]) -> AgentProtocol | None:
    if payload.get("enabled") is False:
        return None

    runtime = _normalize_manifest_runtime(payload.get("runtime"))
    name = str(payload.get("name") or "").strip()
    if not _AGENT_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "Agent plugin manifest name must be 1-64 characters and use only "
            "letters, numbers, dots, underscores, or hyphens"
        )

    capabilities = _normalize_manifest_strings(
        payload.get("capabilities"),
        field_name="capabilities",
    )
    description = str(payload.get("description") or "").strip()
    if not description:
        raise ValueError("Agent plugin manifest field 'description' cannot be empty")

    output_prefix = str(
        payload.get("output_prefix") or f"{name} plugin completed task"
    ).strip()
    if not output_prefix:
        output_prefix = f"{name} plugin completed task"

    manifest_metadata = _safe_manifest_metadata(payload.get("metadata"))
    version = str(payload.get("version") or "").strip()
    if version:
        manifest_metadata["version"] = version

    risk_level = _normalize_manifest_risk_level(
        payload.get("risk_level")
        or manifest_metadata.get("risk_level")
        or manifest_metadata.get("risk")
    )
    if risk_level:
        manifest_metadata["risk_level"] = risk_level

    if "requires_approval" in payload:
        manifest_metadata["requires_approval"] = bool(payload.get("requires_approval"))
    if "approval_reason" in payload:
        approval_reason = str(payload.get("approval_reason") or "").strip()
        if approval_reason:
            manifest_metadata["approval_reason"] = approval_reason

    return StaticAgent(
        name=name,
        description=description,
        capabilities=capabilities,
        output_prefix=output_prefix,
        metadata={
            **manifest_metadata,
            "source": "plugin_manifest",
            "plugin": True,
            "runtime": "static_manifest",
        },
    ) if runtime == "static_manifest" else WorkflowManifestAgent(
        name=name,
        description=description,
        capabilities=capabilities,
        output_prefix=output_prefix,
        workflow=_normalize_manifest_workflow(payload.get("workflow")),
        metadata={
            **manifest_metadata,
            "source": "plugin_manifest",
            "plugin": True,
            "runtime": "workflow_manifest",
        },
    )


def _manifest_issue(
    manifest_path: Path,
    *,
    code: str,
    message: str,
) -> AgentPluginManifestIssue:
    return AgentPluginManifestIssue(
        file=str(manifest_path),
        code=code,
        message=message,
    )


def load_agent_plugin_manifest_report(
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> AgentPluginManifestLoadReport:
    """Load manifest agents plus diagnostics without importing plugin code."""

    directories = (
        [Path(item).expanduser() for item in plugin_dirs]
        if plugin_dirs is not None
        else default_agent_plugin_dirs()
    )
    report = AgentPluginManifestLoadReport(directories=directories)
    if not agent_plugin_manifests_enabled():
        return report

    seen_names: set[str] = set()
    for directory in directories:
        if not directory.exists() or not directory.is_dir():
            continue
        for manifest_path in sorted(directory.glob("*.json")):
            report.scanned_count += 1
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Agent plugin manifest root must be an object")
                agent = _agent_from_manifest(payload)
            except json.JSONDecodeError as exc:
                report.issues.append(
                    _manifest_issue(
                        manifest_path,
                        code="invalid_json",
                        message=str(exc),
                    )
                )
                continue
            except Exception as exc:
                report.issues.append(
                    _manifest_issue(
                        manifest_path,
                        code="invalid_manifest",
                        message=f"Manifest does not match the Agent plugin schema: {exc}",
                    )
                )
                continue
            if agent is None or agent.name in seen_names:
                if agent is not None and agent.name in seen_names:
                    report.issues.append(
                        _manifest_issue(
                            manifest_path,
                            code="duplicate_name",
                            message=f"Duplicate Agent plugin name skipped: {agent.name}",
                        )
                    )
                continue
            seen_names.add(agent.name)
            report.agents.append(agent)
    return report


def load_agent_plugin_manifests(
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> list[AgentProtocol]:
    """Load declarative Agent plugin manifests without importing or executing code."""

    return load_agent_plugin_manifest_report(plugin_dirs).agents


def register_agent_plugin_manifests(
    registry: AgentRegistry,
    *,
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> list[AgentProtocol]:
    """Register valid plugin manifests and skip duplicates to keep startup safe."""

    registered: list[AgentProtocol] = []
    for agent in load_agent_plugin_manifests(plugin_dirs):
        try:
            registry.register(agent)
        except ValueError:
            continue
        registered.append(agent)
    return registered


def _agent_plugin_install_dir(
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> Path:
    directories = (
        [Path(item).expanduser() for item in plugin_dirs]
        if plugin_dirs is not None
        else default_agent_plugin_dirs()
    )
    if not directories:
        raise ValueError("Agent plugin manifest directory is required")
    return directories[0]


def _sanitized_agent_plugin_manifest(manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(manifest, dict):
        raise ValueError("Agent plugin manifest must be a JSON object")
    if manifest.get("enabled") is False:
        raise ValueError("Agent plugin install requires an enabled manifest")

    agent = _agent_from_manifest(manifest)
    if agent is None:
        raise ValueError("Agent plugin install requires an enabled manifest")

    try:
        create_default_agent_registry(include_plugin_manifests=False).get(agent.name)
    except KeyError:
        pass
    else:
        raise ValueError(f"Agent plugin name conflicts with built-in agent: {agent.name}")

    safe_metadata = {
        key: value
        for key, value in _safe_manifest_metadata(manifest.get("metadata")).items()
        if key not in _PLUGIN_METADATA_RESERVED_KEYS
    }
    sanitized: dict[str, Any] = {
        "enabled": True,
        "name": agent.name,
        "description": agent.description,
        "capabilities": list(agent.capabilities),
    }

    version = str(manifest.get("version") or "").strip()
    if version:
        sanitized["version"] = version
    output_prefix = str(manifest.get("output_prefix") or "").strip()
    if output_prefix:
        sanitized["output_prefix"] = output_prefix
    if isinstance(agent, WorkflowManifestAgent):
        sanitized["runtime"] = "workflow_manifest"
        sanitized["workflow"] = [dict(step) for step in agent.workflow]
    risk_level = str(agent.metadata.get("risk_level") or "").strip()
    if risk_level:
        sanitized["risk_level"] = risk_level
    if "requires_approval" in agent.metadata:
        sanitized["requires_approval"] = bool(agent.metadata.get("requires_approval"))
    approval_reason = str(agent.metadata.get("approval_reason") or "").strip()
    if approval_reason:
        sanitized["approval_reason"] = approval_reason
    if safe_metadata:
        sanitized["metadata"] = safe_metadata

    return agent.name, sanitized


def _marketplace_template_item(
    manifest: dict[str, Any],
    *,
    source: str,
    installed_names: set[str],
) -> dict[str, Any]:
    installable_manifest = {**manifest, "enabled": True}
    agent_name, sanitized = _sanitized_agent_plugin_manifest(installable_manifest)
    metadata = sanitized.get("metadata") if isinstance(sanitized.get("metadata"), dict) else {}
    risk_level = str(sanitized.get("risk_level") or "medium").strip() or "medium"
    category = str(
        installable_manifest.get("category")
        or metadata.get("category")
        or "custom"
    ).strip() or "custom"
    return {
        "name": agent_name,
        "description": str(sanitized.get("description") or ""),
        "capabilities": list(sanitized.get("capabilities", [])),
        "category": category,
        "risk_level": risk_level,
        "requires_approval": bool(sanitized.get("requires_approval", False)),
        "approval_reason": str(sanitized.get("approval_reason") or ""),
        "source": source,
        "installed": agent_name in installed_names,
        "template": True,
        "manifest": sanitized,
    }


def list_agent_plugin_marketplace(
    *,
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
    marketplace_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
    installed_names: set[str] | None = None,
) -> dict[str, Any]:
    """Return installable Agent plugin templates without executing plugin code."""

    if installed_names is None:
        installed_names = {
            agent.name for agent in load_agent_plugin_manifest_report(plugin_dirs).agents
        }

    directories = (
        [Path(item).expanduser() for item in marketplace_dirs]
        if marketplace_dirs is not None
        else default_agent_plugin_marketplace_dirs()
    )
    example_dirs = (
        [Path(item).expanduser() for item in plugin_dirs]
        if plugin_dirs is not None
        else default_agent_plugin_dirs()
    )
    templates: list[dict[str, Any]] = []
    issues: list[AgentPluginManifestIssue] = []
    seen_names: set[str] = set()

    def add_template(raw_manifest: dict[str, Any], source: str, issue_path: Path) -> None:
        try:
            item = _marketplace_template_item(
                raw_manifest,
                source=source,
                installed_names=installed_names or set(),
            )
        except Exception as exc:
            issues.append(
                _manifest_issue(
                    issue_path,
                    code="invalid_marketplace_template",
                    message=str(exc),
                )
            )
            return
        if item["name"] in seen_names:
            return
        seen_names.add(item["name"])
        templates.append(item)

    for index, manifest in enumerate(_BUILTIN_AGENT_PLUGIN_MARKETPLACE_TEMPLATES):
        add_template(dict(manifest), "builtin", Path(f"builtin-agent-template-{index}.json"))

    for directory in directories:
        if not directory.exists() or not directory.is_dir():
            continue
        for manifest_path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Agent plugin marketplace template root must be an object")
            except Exception as exc:
                issues.append(
                    _manifest_issue(
                        manifest_path,
                        code="invalid_marketplace_json",
                        message=str(exc),
                    )
                )
                continue
            add_template(payload, str(manifest_path), manifest_path)

    for directory in example_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for manifest_path in sorted(directory.glob("*.example.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Agent plugin example template root must be an object")
            except Exception as exc:
                issues.append(
                    _manifest_issue(
                        manifest_path,
                        code="invalid_example_json",
                        message=str(exc),
                    )
                )
                continue
            add_template(payload, str(manifest_path), manifest_path)

    categories = {str(item.get("category") or "custom") for item in templates}
    installed_count = sum(1 for item in templates if item.get("installed"))
    return {
        "templates": templates,
        "summary": {
            "total": len(templates),
            "installed": installed_count,
            "available": len(templates) - installed_count,
            "categories": len(categories),
            "issue_count": len(issues),
        },
        "issues": [issue.as_dict() for issue in issues],
    }


def install_agent_plugin_manifest_payload(
    manifest: dict[str, Any],
    *,
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    """Persist a declarative Agent plugin manifest without importing code."""

    agent_name, sanitized = _sanitized_agent_plugin_manifest(manifest)
    install_dir = _agent_plugin_install_dir(plugin_dirs)
    install_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = install_dir / f"{agent_name}.json"
    tmp_path = manifest_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(manifest_path)

    catalog = list_agent_catalog(plugin_dirs=plugin_dirs)
    installed = next(
        (
            item
            for item in catalog.get("agents", [])
            if isinstance(item, dict) and item.get("name") == agent_name
        ),
        {
            "name": agent_name,
            "description": sanitized.get("description", ""),
            "capabilities": list(sanitized.get("capabilities", [])),
            "metadata": {},
        },
    )
    catalog["installed"] = {
        "name": agent_name,
        "agent": installed,
        "manifest_path": str(manifest_path),
        "executed_entrypoint": False,
    }
    return catalog


def uninstall_agent_plugin_manifest_payload(
    name: str,
    *,
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    """Delete a declared Agent plugin manifest without touching plugin code."""

    agent_name = str(name or "").strip()
    if not _AGENT_NAME_PATTERN.fullmatch(agent_name):
        raise ValueError(
            "Agent plugin manifest name must be 1-64 characters and use only "
            "letters, numbers, dots, underscores, or hyphens"
        )
    try:
        create_default_agent_registry(include_plugin_manifests=False).get(agent_name)
    except KeyError:
        pass
    else:
        raise ValueError(f"Agent plugin name conflicts with built-in agent: {agent_name}")

    install_dir = _agent_plugin_install_dir(plugin_dirs)
    manifest_path = install_dir / f"{agent_name}.json"
    existed = manifest_path.exists()
    if not existed:
        raise ValueError(f"Agent plugin manifest not found: {agent_name}")

    manifest_path.unlink()
    catalog = list_agent_catalog(plugin_dirs=plugin_dirs)
    catalog["uninstalled"] = {
        "name": agent_name,
        "manifest_path": str(manifest_path),
        "deleted_manifest": True,
        "existed": existed,
    }
    return catalog


def list_agent_catalog(
    *,
    plugin_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    registry = create_default_agent_registry(plugin_dirs=plugin_dirs)
    agents = registry.describe_agents()
    plugin_count = sum(
        1
        for agent in agents
        if bool((agent.get("metadata") or {}).get("plugin"))
        or (agent.get("metadata") or {}).get("source") == "plugin_manifest"
    )
    directories = (
        default_agent_plugin_dirs()
        if plugin_dirs is None
        else [Path(item).expanduser() for item in plugin_dirs]
    )
    manifest_report = load_agent_plugin_manifest_report(plugin_dirs)
    installed_names = {
        str(agent.get("name") or "")
        for agent in agents
        if bool((agent.get("metadata") or {}).get("plugin"))
        or (agent.get("metadata") or {}).get("source") == "plugin_manifest"
    }
    return {
        "agents": agents,
        "summary": {
            "total": len(agents),
            "builtin": len(agents) - plugin_count,
            "plugin": plugin_count,
        },
        "plugin_manifests": {
            "enabled": agent_plugin_manifests_enabled(),
            "directory_count": len(directories),
            "scanned_count": manifest_report.scanned_count,
            "loaded_count": len(manifest_report.agents),
            "issue_count": len(manifest_report.issues),
            "issues": [issue.as_dict() for issue in manifest_report.issues],
        },
        "marketplace": list_agent_plugin_marketplace(
            plugin_dirs=plugin_dirs,
            installed_names=installed_names,
        ),
    }
