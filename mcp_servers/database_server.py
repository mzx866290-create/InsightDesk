"""Minimal built-in database MCP server.

This server intentionally avoids real database connections. It exists so the
built-in connector is discoverable and can report static readiness.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("database")


@mcp.tool()
async def database_status() -> str:
    """Return static database connector status without opening a connection."""

    return "Database connector is available for catalog and static health checks."


if __name__ == "__main__":
    mcp.run(transport="stdio")
