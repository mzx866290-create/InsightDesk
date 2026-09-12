"""Secret redaction for MCP server configuration values.

Extracted from backend.agent_mcp_helpers as a leaf module: these helpers
only depend on each other and on the module constants below.
"""

from __future__ import annotations

from typing import Any

MCP_CONFIG_REDACTED_VALUE = "***redacted***"

def _mcp_config_contains_secret_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    if normalized in {"env", "headers", "authorization", "proxy_authorization"}:
        return True
    return any(
        marker in normalized
        for marker in (
            "api_key",
            "apikey",
            "auth",
            "credential",
            "password",
            "private_key",
            "secret",
            "token",
        )
    )


_MCP_URL_QUERY_SECRET_MARKERS = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "credential",
    "key",
    "password",
    "secret",
    "signature",
    "sig",
    "token",
)
_MCP_CLI_SECRET_FLAG_MARKERS = (
    "api-key",
    "apikey",
    "auth",
    "credential",
    "password",
    "secret",
    "token",
    "private-key",
    "bearer",
)
_MCP_URL_STRING_KEYS = {"url", "uri", "endpoint", "base_url", "callback", "webhook"}


def _redact_url_embedded_secret(text: str) -> str:
    """Replace query/fragment content that may carry credentials in a URL value."""
    if not isinstance(text, str) or "://" not in text:
        return text
    query_start = text.find("?")
    fragment_start = text.find("#")
    if query_start < 0 and fragment_start < 0:
        return text
    if query_start >= 0:
        sensitive_tail = text[query_start:]
    else:
        sensitive_tail = text[fragment_start:]
    lower_tail = sensitive_tail.lower()
    if any(
        marker in lower_tail
        for marker in _MCP_URL_QUERY_SECRET_MARKERS
    ):
        head_end = query_start if query_start >= 0 else fragment_start
        return f"{text[:head_end]}***redacted***"
    return text


def _redact_cli_args(args: list[Any]) -> list[Any]:
    """Redact ``--flag value`` and ``--flag=value`` secret forms in CLI args."""
    redacted: list[Any] = []
    previous_was_secret_flag = False
    for item in args:
        text = str(item)
        stripped = text.strip()
        if previous_was_secret_flag and not text.startswith("-"):
            redacted.append(MCP_CONFIG_REDACTED_VALUE)
            previous_was_secret_flag = False
            continue
        previous_was_secret_flag = False
        if "=" in stripped:
            flag, _separator, value = stripped.partition("=")
            flag_name = flag.lstrip("-").lower()
            if value and any(
                marker in flag_name for marker in _MCP_CLI_SECRET_FLAG_MARKERS
            ):
                redacted.append(f"{flag}={MCP_CONFIG_REDACTED_VALUE}")
                continue
        elif text.startswith("-"):
            flag_name = stripped.lstrip("-").lower()
            if any(
                marker in flag_name for marker in _MCP_CLI_SECRET_FLAG_MARKERS
            ):
                redacted.append(text)
                previous_was_secret_flag = True
                continue
        redacted.append(item)
    if previous_was_secret_flag:
        redacted.append(MCP_CONFIG_REDACTED_VALUE)
    return redacted


def _redact_mcp_config_value(value: Any, *, force: bool = False, key: Any = None) -> Any:
    if isinstance(value, dict):
        return {
            str(child_key): _redact_mcp_config_value(
                item,
                force=force or _mcp_config_contains_secret_key(child_key),
                key=child_key,
            )
            for child_key, item in value.items()
        }
    if isinstance(value, list):
        if force:
            return [
                MCP_CONFIG_REDACTED_VALUE
                if isinstance(item, (str, int, float))
                else _redact_mcp_config_value(item, force=True)
                for item in value
            ]
        return _redact_cli_args(
            [_redact_mcp_config_value(item, force=False) for item in value]
        )
    if force and value not in (None, ""):
        return MCP_CONFIG_REDACTED_VALUE
    if isinstance(value, str) and not force and key is not None:
        normalized_key = str(key or "").strip().lower().replace("-", "_")
        if normalized_key in _MCP_URL_STRING_KEYS:
            return _redact_url_embedded_secret(value)
    return value


def redact_mcp_server_config(config: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(server_name): _redact_mcp_config_value(dict(connection))
        for server_name, connection in config.items()
        if isinstance(connection, dict)
    }


def _merge_redacted_mcp_config_value(new_value: Any, previous_value: Any) -> Any:
    if new_value == MCP_CONFIG_REDACTED_VALUE:
        return previous_value
    if isinstance(new_value, dict):
        previous_mapping = previous_value if isinstance(previous_value, dict) else {}
        return {
            str(key): _merge_redacted_mcp_config_value(
                item,
                previous_mapping.get(key),
            )
            for key, item in new_value.items()
        }
    if isinstance(new_value, list):
        previous_items = previous_value if isinstance(previous_value, list) else []
        return [
            _merge_redacted_mcp_config_value(
                item,
                previous_items[index] if index < len(previous_items) else None,
            )
            for index, item in enumerate(new_value)
        ]
    return new_value


