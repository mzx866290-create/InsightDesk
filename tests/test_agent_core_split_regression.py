import ast
import importlib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


REGRESSION_MATRIX = [
    pytest.param(
        "backend.agent_core",
        "build_agent",
        "backend.agent.builder",
        "build_agent",
        id="builder.build_agent",
    ),
    pytest.param(
        "backend.agent_core",
        "test_agent",
        "backend.agent.builder",
        "test_agent",
        id="builder.test_agent",
    ),
    pytest.param(
        "backend.agent_core",
        "build_agent",
        "backend.agent",
        "build_agent",
        id="package.build_agent",
    ),
    pytest.param(
        "backend.agent_core",
        "build_runtime_tools",
        "backend.agent.runtime_tools",
        "build_runtime_tools",
        id="runtime_tools.build_runtime_tools",
    ),
    pytest.param(
        "backend.agent_core",
        "create_tools",
        "backend.agent.tools",
        "create_tools",
        id="tools.create_tools",
    ),
    pytest.param(
        "backend.agent_core",
        "list_enabled_builtin_tool_specs",
        "backend.agent.tool_registry",
        "list_enabled_builtin_tool_specs",
        id="tool_registry.list_enabled_builtin_tool_specs",
    ),
    pytest.param(
        "backend.agent_core",
        "load_mcp_tool_overrides",
        "backend.agent_mcp_helpers",
        "load_mcp_tool_overrides",
        id="mcp.load_mcp_tool_overrides",
    ),
    pytest.param(
        "backend.agent_core",
        "build_langgraph_agent",
        "backend.agent.langgraph",
        "build_langgraph_agent",
        id="langgraph.build_langgraph_agent",
    ),
    pytest.param(
        "backend.agent_core",
        "AgentState",
        "backend.agent.langgraph_helpers",
        "AgentState",
        id="langgraph_helpers.AgentState",
    ),
    pytest.param(
        "backend.agent_core",
        "_rewrite_search_query",
        "backend.agent.langgraph_helpers",
        "_rewrite_search_query",
        id="langgraph_helpers.rewrite_search_query",
    ),
    pytest.param(
        "backend.agent_core",
        "_heuristic_langgraph_tool_choice",
        "backend.agent.runtime_plain_chat",
        "_heuristic_langgraph_tool_choice",
        id="plain_chat.heuristic_tool_choice",
    ),
    pytest.param(
        "backend.agent_core",
        "_should_bypass_tools_for_plain_text_chat",
        "backend.agent.runtime_plain_chat",
        "_should_bypass_tools_for_plain_text_chat",
        id="plain_chat.should_bypass_tools",
    ),
    pytest.param(
        "backend.agent_core",
        "_build_plain_text_chat_messages",
        "backend.agent.runtime_plain_chat",
        "_build_plain_text_chat_messages",
        id="plain_chat.build_messages",
    ),
    pytest.param(
        "backend.agent_core",
        "_direct_plain_text_answer",
        "backend.agent.runtime_plain_chat",
        "_direct_plain_text_answer",
        id="plain_chat.direct_answer",
    ),
    pytest.param(
        "backend.agent_core",
        "_astream_plain_text_answer",
        "backend.agent.runtime_plain_chat",
        "_astream_plain_text_answer",
        id="plain_chat.stream_answer",
    ),
    pytest.param(
        "backend.agent_core",
        "_should_generate_dashboard",
        "backend.agent.dashboard_payload",
        "_should_generate_dashboard",
        id="dashboard_payload.should_generate_dashboard",
    ),
    pytest.param(
        "backend.agent_core",
        "_extract_json_payload",
        "backend.agent.dashboard_payload",
        "_extract_json_payload",
        id="dashboard_payload.extract_json",
    ),
    pytest.param(
        "backend.agent_core",
        "_generate_dashboard_from_attachment",
        "backend.agent.dashboard",
        "_generate_dashboard_from_attachment",
        id="dashboard.generate_from_attachment",
    ),
    pytest.param(
        "backend.agent_core",
        "_generate_dashboard_from_knowledge",
        "backend.agent.dashboard",
        "_generate_dashboard_from_knowledge",
        id="dashboard.generate_from_knowledge",
    ),
    pytest.param(
        "backend.agent_core",
        "_extract_attachment_evidence",
        "backend.agent.dashboard_attachments",
        "_extract_attachment_evidence",
        id="dashboard_attachments.extract_evidence",
    ),
    pytest.param(
        "backend.agent_core",
        "create_runtime_agent_registry",
        "backend.agent.registry",
        "create_runtime_agent_registry",
        id="registry.create_runtime_agent_registry",
    ),
    pytest.param(
        "backend.agent_core",
        "run_orchestrator",
        "backend.agent.orchestrator",
        "run_orchestrator",
        id="orchestrator.run_orchestrator",
    ),
]


DIRECT_IMPORT_MODULES = [
    "backend.agent.builder",
    "backend.agent.runtime_tools",
    "backend.agent.tools",
    "backend.agent.tool_registry",
    "backend.agent.langgraph",
    "backend.agent.langgraph_helpers",
    "backend.agent.runtime_plain_chat",
    "backend.agent.dashboard",
    "backend.agent.dashboard_payload",
    "backend.agent.dashboard_attachments",
    "backend.agent.registry",
    "backend.agent.orchestrator",
]


STATIC_CONTRACTS = {
    "backend/agent_core.py": {
        "max_lines": 90,
        "max_top_level_defs": 1,
        "allowed_import_roots": {"sys", "types", "backend.agent"},
    },
    "backend/agent/runtime_support.py": {
        "max_lines": 220,
        "max_top_level_defs": 0,
        "forbidden_top_level_defs": {
            "build_agent",
            "test_agent",
            "build_langgraph_agent",
            "build_runtime_tools",
            "create_tools",
        },
    },
    "backend/agent/langgraph.py": {
        "max_lines": 650,
        "max_top_level_defs": 1,
        "forbidden_top_level_defs": {
            "build_agent",
            "test_agent",
            "build_runtime_tools",
            "create_tools",
        },
    },
}


@pytest.mark.parametrize(
    "legacy_module_name,legacy_name,split_module_name,split_name",
    REGRESSION_MATRIX,
)
def test_agent_core_split_regression_matrix_exports_same_objects(
    legacy_module_name,
    legacy_name,
    split_module_name,
    split_name,
):
    legacy_module = importlib.import_module(legacy_module_name)
    split_module = importlib.import_module(split_module_name)

    assert getattr(legacy_module, legacy_name) is getattr(split_module, split_name)


@pytest.mark.parametrize("module_name", DIRECT_IMPORT_MODULES)
def test_agent_core_split_modules_remain_directly_importable(module_name):
    module = importlib.import_module(module_name)

    assert module.__name__ == module_name


def test_agent_core_behavior_matches_split_dashboard_payload_helpers():
    legacy = importlib.import_module("backend.agent_core")
    payload = importlib.import_module("backend.agent.dashboard_payload")

    raw = 'prefix ```json\n{"title":"Ops","summary":"ok","evidence":[]}\n``` suffix'

    assert legacy._extract_json_payload(raw) == payload._extract_json_payload(raw)
    assert legacy._normalize_dashboard_template({"title_hint": "Ops"}) == (
        payload._normalize_dashboard_template({"title_hint": "Ops"})
    )
    assert legacy._should_generate_dashboard("please generate a dashboard") == (
        payload._should_generate_dashboard("please generate a dashboard")
    )


def test_agent_core_behavior_matches_split_plain_chat_helpers():
    legacy = importlib.import_module("backend.agent_core")
    plain_chat = importlib.import_module("backend.agent.runtime_plain_chat")

    user_input = "hello, answer directly"

    assert legacy._should_bypass_tools_for_plain_text_chat(
        user_input,
        knowledge_base_enabled=True,
        web_search_enabled=True,
    ) == plain_chat._should_bypass_tools_for_plain_text_chat(
        user_input,
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )
    assert legacy._heuristic_langgraph_tool_choice(
        user_input,
        knowledge_base_enabled=True,
        web_search_enabled=True,
    ) == plain_chat._heuristic_langgraph_tool_choice(
        user_input,
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )


def test_agent_history_entrypoints_use_chat_history_factory():
    history_source = (PROJECT_ROOT / "backend/agent/history.py").read_text(
        encoding="utf-8"
    )
    builder_history_source = (
        PROJECT_ROOT / "backend/agent/builder_history.py"
    ).read_text(encoding="utf-8")

    assert "backend.stores.factory import create_chat_message_history" in history_source
    assert "SQLiteChatMessageHistory" not in history_source
    assert "runtime_support.create_chat_message_history" in builder_history_source
    assert "runtime_support.SQLiteChatMessageHistory" not in builder_history_source


def test_legacy_agent_core_monkeypatch_reaches_key_split_entrypoints(monkeypatch):
    legacy = importlib.import_module("backend.agent_core")
    builder = importlib.import_module("backend.agent.builder")
    langgraph = importlib.import_module("backend.agent.langgraph")
    runtime_tools = importlib.import_module("backend.agent.runtime_tools")

    async def sentinel_runtime_tools(*_args, **_kwargs):
        return ["sentinel"]

    def sentinel_build_agent(*_args, **_kwargs):
        return "sentinel-agent"

    monkeypatch.setattr(legacy, "build_runtime_tools", sentinel_runtime_tools)
    monkeypatch.setattr(legacy, "build_agent", sentinel_build_agent)

    assert runtime_tools.build_runtime_tools is sentinel_runtime_tools
    assert langgraph.build_runtime_tools is sentinel_runtime_tools
    assert builder.build_runtime_tools is sentinel_runtime_tools
    assert builder.build_agent is sentinel_build_agent


@pytest.mark.parametrize("relative_path,contract", STATIC_CONTRACTS.items())
def test_agent_core_split_static_file_boundaries(relative_path, contract):
    path = PROJECT_ROOT / relative_path
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    top_level_defs = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    assert len(source.splitlines()) <= contract["max_lines"]
    assert len(top_level_defs) <= contract["max_top_level_defs"]
    assert not (set(top_level_defs) & set(contract.get("forbidden_top_level_defs", set())))

    allowed_import_roots = contract.get("allowed_import_roots")
    if allowed_import_roots is None:
        return

    imported_roots = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module)

    assert imported_roots <= allowed_import_roots
