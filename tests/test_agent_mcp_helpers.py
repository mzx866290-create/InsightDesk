import asyncio
import json
import sys

from backend.agent_mcp_helpers import (
    default_mcp_connections,
    list_mcp_server_catalog,
    load_mcp_connection_config,
    load_mcp_tool_overrides,
    select_mcp_connections,
)


def test_default_mcp_connections_discovers_repo_scripts(tmp_path):
    mcp_dir = tmp_path / "mcp_servers"
    mcp_dir.mkdir()
    (mcp_dir / "knowledge_server.py").write_text("print('knowledge')", encoding="utf-8")
    (mcp_dir / "search_server.py").write_text("print('search')", encoding="utf-8")

    connections = default_mcp_connections(
        project_root=tmp_path,
        python_command="python",
    )

    assert set(connections) == {"knowledge-base", "web-search"}
    assert connections["knowledge-base"]["args"] == [
        str((mcp_dir / "knowledge_server.py").resolve())
    ]
    assert connections["web-search"]["cwd"] == str(tmp_path)


def test_load_mcp_connection_config_resolves_relative_paths(tmp_path):
    config_path = tmp_path / "config" / "mcp.json"
    config_path.parent.mkdir()
    server_script = tmp_path / "servers" / "custom_server.py"
    server_script.parent.mkdir()
    server_script.write_text("print('server')", encoding="utf-8")
    (tmp_path / "runtime").mkdir()

    config_path.write_text(
        json.dumps(
            {
                "custom": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["../servers/custom_server.py"],
                    "cwd": "../runtime",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    connections = load_mcp_connection_config(str(config_path), project_root=tmp_path)

    assert connections["custom"]["args"] == [str(server_script.resolve())]
    assert connections["custom"]["cwd"] == str((tmp_path / "runtime").resolve())


def test_select_mcp_connections_honors_enablement_and_server_filters(monkeypatch, tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "knowledge-base": {"transport": "stdio", "command": "python", "args": ["kb.py"]},
                "web-search": {"transport": "stdio", "command": "python", "args": ["web.py"]},
                "custom": {"transport": "stdio", "command": "python", "args": ["custom.py"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("ENABLE_MCP_TOOLS", "true")
    monkeypatch.setenv("MCP_SERVER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ENABLED_MCP_SERVERS", "web-search, custom, missing")

    connections = select_mcp_connections(
        knowledge_base_enabled=False,
        web_search_enabled=True,
        project_root=tmp_path,
    )

    assert set(connections) == {"web-search", "custom"}


def test_select_mcp_connections_supports_explicit_enabled_servers_without_env(monkeypatch, tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "knowledge-base": {"transport": "stdio", "command": "python", "args": ["kb.py"]},
                "custom": {"transport": "stdio", "command": "python", "args": ["custom.py"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("ENABLE_MCP_TOOLS", raising=False)
    monkeypatch.delenv("ENABLED_MCP_SERVERS", raising=False)

    connections = select_mcp_connections(
        knowledge_base_enabled=True,
        web_search_enabled=False,
        project_root=tmp_path,
        config_path=str(config_path),
        enabled_server_names=["custom", "missing"],
    )

    assert set(connections) == {"custom"}


def test_list_mcp_server_catalog_includes_default_source_and_metadata(tmp_path):
    mcp_dir = tmp_path / "mcp_servers"
    mcp_dir.mkdir()
    (mcp_dir / "knowledge_server.py").write_text("print('knowledge')", encoding="utf-8")
    (mcp_dir / "search_server.py").write_text("print('search')", encoding="utf-8")

    catalog = list_mcp_server_catalog(
        project_root=tmp_path,
        python_command="python",
    )

    assert [item["name"] for item in catalog] == ["knowledge-base", "web-search"]
    assert all(item["source"] == "default" for item in catalog)
    assert catalog[0]["label"] == "Knowledge Base"
    assert catalog[1]["label"] == "Web Search"


def test_load_mcp_tool_overrides_filters_expected_names():
    class FakeTool:
        def __init__(self, name: str):
            self.name = name

    class FakeClient:
        def __init__(self, connections, tool_name_prefix=False):
            self.connections = connections
            self.tool_name_prefix = tool_name_prefix

        async def get_tools(self):
            return [FakeTool("web_search"), FakeTool("custom_tool")]

    async def run():
        return await load_mcp_tool_overrides(
            connections={"web-search": {"transport": "stdio", "command": "python", "args": []}},
            expected_tool_names={"web_search"},
            client_factory=FakeClient,
        )

    tools = asyncio.run(run())

    assert set(tools) == {"web_search"}


def test_load_mcp_tool_overrides_supports_real_stdio_server(tmp_path):
    server_script = tmp_path / "fake_mcp_server.py"
    server_script.write_text(
        """
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fake")

@mcp.tool()
async def web_search(search_query: str) -> str:
    return f"echo:{search_query}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
""".strip(),
        encoding="utf-8",
    )

    async def run():
        tools = await load_mcp_tool_overrides(
            connections={
                "fake": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(server_script)],
                    "cwd": str(tmp_path),
                    "encoding": "utf-8",
                }
            },
            expected_tool_names={"web_search"},
        )
        tool = tools["web_search"]
        assert "search_query" in tool.args
        assert await tool.ainvoke({"search_query": "hello"}) == "echo:hello"

    asyncio.run(run())
