"""common helpers for MCP connector management."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)


from backend.mcp_helpers.allowlist import (  # noqa: F401
    parse_name_list,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_SERVER_CONFIG_FILENAME = "mcp_server_config.json"
MCP_CONNECTOR_METADATA_KEYS = {
    "label",
    "description",
    "category",
    "builtin",
    "capability_scopes",
    "risk_level",
    "requires_approval",
    "config_schema",
}
MCP_RISK_LEVELS = {"low", "medium", "high", "critical"}
MCP_APPROVAL_RISK_LEVELS = {"high", "critical"}
MCP_CONNECTOR_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MCP_MARKET_CATEGORY_LABELS = {
    "data": "Data",
    "development": "Development",
    "documents": "Documents",
    "files": "Files",
    "platform": "Platform",
    "productivity": "Productivity",
    "communication": "Communication",
    "custom": "Custom",
}
class McpConnectorManifestError(ValueError):
    """Validation error with stable fields for marketplace manifest UX."""

    def __init__(self, code: str, message: str, *, field: str = "manifest"):
        super().__init__(message)
        self.code = code
        self.field = field
        self.message = message

    def to_api_detail(self) -> dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }
def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
def _env_name_list(name: str) -> list[str] | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return parse_name_list(raw)
def _env_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default
def default_mcp_server_config_path(*, project_root: Path = PROJECT_ROOT) -> Path:
    return project_root / "runtime" / MCP_SERVER_CONFIG_FILENAME
def _active_mcp_server_config_path(
    *,
    project_root: Path = PROJECT_ROOT,
    config_path: str | None = None,
    for_write: bool = False,
) -> Path | None:
    raw_path = str(config_path or os.getenv("MCP_SERVER_CONFIG_PATH") or "").strip()
    if raw_path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (project_root / path).resolve()
        return path

    default_path = default_mcp_server_config_path(project_root=project_root)
    if for_write or default_path.is_file():
        return default_path
    return None
