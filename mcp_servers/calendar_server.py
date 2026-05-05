"""Minimal built-in calendar MCP server.

This server intentionally avoids real calendar-provider dependencies.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calendar")


@mcp.tool()
async def calendar_status() -> str:
    """Return static calendar connector status without provider access."""

    return "Calendar connector is available for catalog and static health checks."


if __name__ == "__main__":
    mcp.run(transport="stdio")
