"""Compatibility facade for the MCP helper package.

Implementation lives in backend/mcp_helpers/*; every historical
top-level name stays importable from this module.
"""

from backend.mcp_helpers.common import (  # noqa: F401
    MCP_APPROVAL_RISK_LEVELS,
    MCP_CONNECTOR_METADATA_KEYS,
    MCP_CONNECTOR_NAME_PATTERN,
    MCP_MARKET_CATEGORY_LABELS,
    MCP_RISK_LEVELS,
    MCP_SERVER_CONFIG_FILENAME,
    McpConnectorManifestError,
    PROJECT_ROOT,
    _active_mcp_server_config_path,
    _env_flag,
    _env_name_list,
    _env_positive_float,
    default_mcp_server_config_path,
)
from backend.mcp_helpers.tools import (  # noqa: F401
    _normalize_mcp_tool_result,
    _wrap_mcp_tool,
)
from backend.mcp_helpers.allowlist import (  # noqa: F401
    DEFAULT_MCP_SERVER_NAMES,
    _connector_name_in_approval_list,
    _runtime_mcp_approval_lock,
    _runtime_mcp_approved_connectors,
    add_mcp_approved_connector,
    approve_runtime_mcp_connector,
    clear_runtime_mcp_approved_connectors,
    current_mcp_approved_connector_names,
    current_mcp_approved_connectors_payload,
    default_mcp_server_names,
    get_runtime_mcp_approved_connectors,
    list_mcp_approved_connectors,
    normalize_mcp_approved_connectors,
    normalize_mcp_connector_name,
    parse_name_list,
    remove_mcp_approved_connector,
    revoke_runtime_mcp_connector,
    set_runtime_mcp_approved_connectors,
)
from backend.mcp_helpers.policy import (  # noqa: F401
    MCP_SERVER_METADATA,
    _configured_mcp_connection_issues,
    _connection_mcp_metadata,
    _describe_mcp_connector_payload,
    _infer_mcp_config_schema,
    _mcp_server_is_requested,
    _normalize_bool,
    _normalize_mcp_config_schema,
    _normalize_policy_set,
    _normalize_risk_level,
    _normalize_schema_list,
    _runtime_mcp_connection,
    _scope_allowed,
    default_mcp_connections,
    describe_mcp_server,
    evaluate_mcp_connector_policy,
    list_mcp_connector_template_catalog,
    mcp_server_health_payload,
    normalize_mcp_server_names,
)
from backend.mcp_helpers.manifest import (  # noqa: F401
    _connection_from_mcp_manifest,
    _manifest_install_command_parts,
    _normalize_mcp_manifest_risk_level,
    _require_mcp_manifest_mapping,
    install_mcp_connector_manifest_payload,
    load_mcp_connection_config,
)
from backend.mcp_helpers.catalog import (  # noqa: F401
    _resolve_mcp_connections,
    build_mcp_connector_marketplace,
    list_mcp_server_catalog,
)
from backend.mcp_helpers.config_store import (  # noqa: F401
    current_mcp_server_config_payload,
    normalize_mcp_server_config_payload,
    save_mcp_server_config_payload,
)
from backend.mcp_helpers.health import (  # noqa: F401
    _record_mcp_runtime_health_snapshot_in_memory,
    _runtime_health_history_limit,
    _runtime_mcp_health_history,
    _runtime_mcp_health_history_lock,
    attach_mcp_runtime_health_history,
    build_mcp_runtime_monitor_payload,
    clear_mcp_runtime_health_history,
    get_mcp_runtime_health_history,
    list_mcp_server_health,
    list_mcp_server_runtime_health,
    load_mcp_tool_overrides,
    record_mcp_runtime_health_snapshot,
    select_mcp_connections,
    summarize_mcp_runtime_health,
)
from backend.mcp_config_redaction import (  # noqa: F401
    MCP_CONFIG_REDACTED_VALUE,
    _MCP_CLI_SECRET_FLAG_MARKERS,
    _MCP_URL_QUERY_SECRET_MARKERS,
    _MCP_URL_STRING_KEYS,
    _mcp_config_contains_secret_key,
    _merge_redacted_mcp_config_value,
    _redact_cli_args,
    _redact_mcp_config_value,
    _redact_url_embedded_secret,
    redact_mcp_server_config,
)
