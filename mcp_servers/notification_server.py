"""Minimal built-in notification MCP server.

This server only supports dry-run status and never sends real notifications.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("notification")


@mcp.tool()
async def notification_status() -> str:
    """Return static notification connector status without sending messages."""

    return "Notification connector is available for catalog and static health checks."


if __name__ == "__main__":
    mcp.run(transport="stdio")
