"""Generic webhook connector descriptor."""

from __future__ import annotations

from backend.agent.agents.integrator.connectors.base import ConnectorSpec, describe_connector


def describe(connector: ConnectorSpec) -> dict[str, object]:
    return describe_connector(
        connector,
        capabilities=["push"],
        defaults={"method": "POST", "content_type": "application/json"},
    )


__all__ = ["describe"]
