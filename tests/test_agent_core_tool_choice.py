import asyncio
import json

from backend.agent_core import (
    _heuristic_langgraph_tool_choice,
    _looks_like_reasoning_only_output,
    _strip_think_tags,
    build_runtime_tools,
    create_tools,
    list_enabled_builtin_tool_specs,
)


def test_kb_question_prefers_query_tool():
    choice = _heuristic_langgraph_tool_choice(
        "你没有读取到我的知识库吗",
        knowledge_base_enabled=True,
        web_search_enabled=False,
    )
    assert choice == "1"


def test_resume_rewrite_prefers_query_tool_for_uploaded_context():
    choice = _heuristic_langgraph_tool_choice(
        "根据我之前上传的简历，帮我重写一版",
        knowledge_base_enabled=True,
        web_search_enabled=False,
    )
    assert choice == "1"


def test_kb_stats_prefers_stats_tool():
    choice = _heuristic_langgraph_tool_choice(
        "知识库现在有多少个文档片段",
        knowledge_base_enabled=True,
        web_search_enabled=False,
    )
    assert choice == "4"


def test_kb_reload_prefers_reload_tool():
    choice = _heuristic_langgraph_tool_choice(
        "帮我刷新一下知识库",
        knowledge_base_enabled=True,
        web_search_enabled=False,
    )
    assert choice == "5"


def test_regular_greeting_keeps_no_forced_tool():
    choice = _heuristic_langgraph_tool_choice(
        "你好",
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )
    assert choice == ""


def test_weather_question_prefers_web_search_tool():
    choice = _heuristic_langgraph_tool_choice(
        "中山天气怎么样",
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )
    assert choice == "2"


def test_strip_think_tags_handles_unclosed_tag():
    assert _strip_think_tags("<think>\ninternal reasoning") == ""


def test_reasoning_only_output_detects_unclosed_think():
    assert _looks_like_reasoning_only_output("<think>\ninternal reasoning") is True


def test_builtin_tool_registry_keeps_expected_codes_and_order():
    specs = list_enabled_builtin_tool_specs(
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )
    assert [(spec.code, spec.name) for spec in specs] == [
        ("1", "query_knowledge"),
        ("4", "get_knowledge_stats"),
        ("5", "reload_knowledge_base"),
        ("2", "web_search"),
        ("3", "quick_answer"),
        ("6", "fetch_webpage"),
    ]


def test_create_tools_filters_disabled_categories():
    class FakePipeline:
        vectorstore = object()
        vector_store_path = "./vector_store"

        def load_store(self):
            return True

        def get_stats(self):
            return {"status": "ready", "total_docs": 1, "store_path": self.vector_store_path}

    tools = create_tools(
        FakePipeline(),
        knowledge_base_enabled=False,
        web_search_enabled=True,
    )
    assert [tool.name for tool in tools] == [
        "web_search",
        "quick_answer",
        "fetch_webpage",
    ]


def test_builtin_tool_registry_honors_env_order_and_filter(monkeypatch):
    monkeypatch.setenv(
        "ENABLED_BUILTIN_TOOLS",
        "quick_answer, query_knowledge ,quick_answer,unknown_tool",
    )

    specs = list_enabled_builtin_tool_specs(
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )

    assert [(spec.code, spec.name) for spec in specs] == [
        ("3", "quick_answer"),
        ("1", "query_knowledge"),
    ]


def test_builtin_tool_registry_uses_json_config_when_env_is_unset(monkeypatch, tmp_path):
    config_path = tmp_path / "builtin_tools.json"
    config_path.write_text(
        json.dumps(
            {"enabled_builtin_tools": ["fetch_webpage", "get_knowledge_stats"]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("ENABLED_BUILTIN_TOOLS", raising=False)
    monkeypatch.setenv("BUILTIN_TOOL_CONFIG_PATH", str(config_path))

    specs = list_enabled_builtin_tool_specs(
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )

    assert [(spec.code, spec.name) for spec in specs] == [
        ("6", "fetch_webpage"),
        ("4", "get_knowledge_stats"),
    ]


def test_builtin_tool_registry_falls_back_to_default_order_for_invalid_json(monkeypatch, tmp_path):
    config_path = tmp_path / "builtin_tools.json"
    config_path.write_text("{invalid-json", encoding="utf-8")
    monkeypatch.delenv("ENABLED_BUILTIN_TOOLS", raising=False)
    monkeypatch.setenv("BUILTIN_TOOL_CONFIG_PATH", str(config_path))

    specs = list_enabled_builtin_tool_specs(
        knowledge_base_enabled=True,
        web_search_enabled=True,
    )

    assert [(spec.code, spec.name) for spec in specs] == [
        ("1", "query_knowledge"),
        ("4", "get_knowledge_stats"),
        ("5", "reload_knowledge_base"),
        ("2", "web_search"),
        ("3", "quick_answer"),
        ("6", "fetch_webpage"),
    ]


def test_build_runtime_tools_overlays_matching_mcp_tools():
    class FakePipeline:
        vectorstore = object()
        vector_store_path = "./vector_store"

        def load_store(self):
            return True

        def get_stats(self):
            return {"status": "ready", "total_docs": 1, "store_path": self.vector_store_path}

    class MCPTool:
        def __init__(self, name: str):
            self.name = name
            self.args = {"search_query": {"type": "string"}}

    async def fake_mcp_loader(**kwargs):
        assert kwargs["expected_tool_names"] is None
        assert kwargs["enabled_server_names"] == ["fetch"]
        return {
            "web_search": MCPTool("web_search"),
            "summarize_results": MCPTool("summarize_results"),
        }

    tools = asyncio.run(
        build_runtime_tools(
            FakePipeline(),
            knowledge_base_enabled=False,
            web_search_enabled=True,
            enabled_mcp_servers=["fetch"],
            mcp_tool_loader=fake_mcp_loader,
        )
    )

    assert [tool.name for tool in tools] == [
        "web_search",
        "quick_answer",
        "fetch_webpage",
        "summarize_results",
    ]
    assert isinstance(tools[0], MCPTool)
    assert isinstance(tools[-1], MCPTool)
