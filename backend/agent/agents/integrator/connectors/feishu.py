"""Feishu connector descriptor."""

from __future__ import annotations

from backend.agent.agents.integrator.connectors.base import ConnectorSpec, describe_connector


def describe(connector: ConnectorSpec) -> dict[str, object]:
    return describe_connector(
        connector,
        capabilities=["push", "sync"],
        defaults={"app": "feishu", "message_type": "interactive_card"},
    )


__all__ = ["describe"]
