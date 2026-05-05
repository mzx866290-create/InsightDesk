"""Protocols shared by multi-agent orchestration components."""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class AgentTask(TypedDict, total=False):
    id: str
    type: str
    description: str
    input: Any
    requires_approval: bool
    metadata: dict[str, Any]


class AgentResult(TypedDict, total=False):
    agent: str
    task_id: str
    task_type: str
    status: str
    output: str
    artifacts: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    error: str
    metadata: dict[str, Any]


class AgentProtocol(Protocol):
    """Minimal contract every specialized business Agent must implement."""

    name: str
    description: str
    capabilities: list[str]

    async def execute(
        self,
        task: AgentTask,
        context: dict[str, Any],
    ) -> AgentResult:
        """Execute one task and return a structured result."""
        ...

    def can_handle(self, task_type: str) -> bool:
        """Return whether this Agent supports the given task type."""
        ...
