"""Request metadata helpers shared by API routes and runtime guards."""

from __future__ import annotations

from fastapi import Request


def request_client_ip(request: Request) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client is not None else ""
    return str(host or "").strip()


def request_user_agent(request: Request) -> str:
    return str(request.headers.get("user-agent") or "").strip()
