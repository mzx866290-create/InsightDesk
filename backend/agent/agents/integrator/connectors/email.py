"""Email connector descriptor."""

from __future__ import annotations

from backend.agent.agents.integrator.connectors.base import ConnectorSpec, describe_connector


def describe(connector: ConnectorSpec) -> dict[str, object]:
    return describe_connector(
        connector,
        capabilities=["push"],
        defaults={"transport": "smtp", "format": "markdown"},
    )


__all__ = ["describe"]
