"""Shared connector descriptors for the Integrator Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SUPPORTED_CONNECTOR_TYPES = ("webhook", "email", "feishu", "dingtalk")
_SECRET_KEYWORDS = (
    "secret",
    "token",
    "password",
    "credential",
    "key",
    "webhook_url",
    "url",
    "authorization",
    "auth",
)


@dataclass(slots=True)
class ConnectorSpec:
    """Configuration-level connector description.

    The spec carries metadata and execution guard flags. Real outbound calls
    are still gated by the Integrator Agent execution switch.
    """

    id: str
    type: str
    name: str = ""
    description: str = ""
    enabled: bool = True
    approved: bool = False
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ConnectorSpec":
        settings = dict(value.get("settings") or {})
        for key, item in value.items():
            if key not in {"id", "type", "name", "description", "enabled", "approved", "settings"}:
                settings.setdefault(str(key), item)
        return cls(
            id=str(value.get("id") or value.get("name") or value.get("type") or "").strip(),
            type=str(value.get("type") or "").strip(),
            name=str(value.get("name") or "").strip(),
            description=str(value.get("description") or "").strip(),
            enabled=coerce_bool(value.get("enabled"), default=True),
            approved=coerce_bool(value.get("approved", settings.get("approved")), default=False),
            settings=settings,
        )

    @property
    def normalized_type(self) -> str:
        return normalize_connector_type(self.type)

    @property
    def display_name(self) -> str:
        return self.name or self.id or self.normalized_type

    def matches(self, selector: str) -> bool:
        normalized = normalize_selector(selector)
        return normalized in {
            normalize_selector(self.id),
            normalize_selector(self.name),
            normalize_selector(self.normalized_type),
            normalize_selector(self.type),
        }


def normalize_connector_type(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    alias_map = {
        "ding_talk": "dingtalk",
        "dingding": "dingtalk",
        "lark": "feishu",
        "mail": "email",
        "http": "webhook",
    }
    return alias_map.get(normalized, normalized)


def normalize_selector(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "enabled", "approved"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled", "rejected"}:
        return False
    return default


def redact_settings(settings: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in settings.items():
        key_text = str(key)
        normalized_key = key_text.lower()
        if any(keyword in normalized_key for keyword in _SECRET_KEYWORDS):
            redacted[key_text] = "***redacted***"
        elif isinstance(value, dict):
            redacted[key_text] = redact_settings(value)
        else:
            redacted[key_text] = value
    return redacted


def describe_connector(
    connector: ConnectorSpec,
    *,
    capabilities: list[str],
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = {**(defaults or {}), **connector.settings}
    return {
        "id": connector.id,
        "type": connector.normalized_type,
        "name": connector.display_name,
        "description": connector.description,
        "enabled": connector.enabled,
        "approved": connector.approved,
        "capabilities": capabilities,
        "dry_run_only": True,
        "settings": redact_settings(settings),
    }
