"""Agent registration and discovery for the multi-agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.agent.agents.data_analysis import DataAnalysisAgent
from backend.agent.agents.integrator import IntegratorAgent, IntegratorAgentConfig
from backend.agent.agents.model_compare import ModelCompareAgent, ModelCompareAgentConfig
from backend.agent.agents.reviewer import ReviewAgent
from backend.agent.agents.researcher import DeepResearchAgent, ResearchAgentConfig
from backend.agent.agents.writer import WritingAgent
from backend.agent.protocols import AgentProtocol, AgentResult, AgentTask


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


def create_default_agent_registry(
    *,
    research_agent: AgentProtocol | None = None,
    data_analysis_agent: AgentProtocol | None = None,
    writing_agent: AgentProtocol | None = None,
    review_agent: AgentProtocol | None = None,
    integrator_agent: AgentProtocol | None = None,
    model_compare_agent: AgentProtocol | None = None,
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
        StaticAgent(
            name="general",
            description="General fallback Agent for tasks without a specialist.",
            capabilities=["general"],
            output_prefix="General Agent completed task handling",
        ),
    ):
        registry.register(agent)
    return registry


def create_runtime_agent_registry(
    *,
    llm: Any | None = None,
    research_config: ResearchAgentConfig | None = None,
    model_compare_config: ModelCompareAgentConfig | None = None,
    integrator_connectors: tuple[Any, ...] | list[Any] | None = None,
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
    )
