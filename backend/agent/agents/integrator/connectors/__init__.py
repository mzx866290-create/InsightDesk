"""Connector descriptor dispatch for Integrator Agent."""

from __future__ import annotations

from backend.agent.agents.integrator.connectors import dingtalk, email, feishu, webhook
from backend.agent.agents.integrator.connectors.base import (
    SUPPORTED_CONNECTOR_TYPES,
    ConnectorSpec,
    normalize_connector_type,
)

_DESCRIBERS = {
    "webhook": webhook.describe,
    "email": email.describe,
    "feishu": feishu.describe,
    "dingtalk": dingtalk.describe,
}


def describe_connector(connector: ConnectorSpec) -> dict[str, object]:
    connector_type = normalize_connector_type(connector.type)
    try:
        describer = _DESCRIBERS[connector_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported connector type: {connector.type}") from exc
    return describer(connector)


__all__ = [
    "SUPPORTED_CONNECTOR_TYPES",
    "ConnectorSpec",
    "describe_connector",
    "normalize_connector_type",
]
