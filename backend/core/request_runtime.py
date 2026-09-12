"""Request metadata helpers shared by API routes and runtime guards.

Reverse-proxy awareness is centralized here so auth, audit, and rate-limit
consumers all see the same notion of where a request came from.

Trust model
-----------
- A request without ``X-Forwarded-For`` is a direct connection and the socket
  peer is authoritative.
- When ``X-Forwarded-For`` is present, the request went through at least one
  proxy. The header is only honored when the direct peer is listed in
  ``TRUSTED_PROXY_IPS``. Without that explicit configuration, a proxied-looking
  request is never treated as local so reverse-proxy deployments cannot
  accidentally inherit loopback admin bypass.
- Trusted proxies must overwrite (or prepend the real client to)
  ``X-Forwarded-For`` and strip client-supplied identity headers at the edge.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Any

from fastapi import Request


def _client_host(request: Request) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client is not None else ""
    return str(host or "").strip()


def _forwarded_for_entries(request: Request) -> list[str]:
    header = str(request.headers.get("x-forwarded-for") or "").strip()
    if not header:
        return []
    return [item.strip() for item in header.split(",") if item.strip()]


def _configured_trusted_proxies() -> list[ipaddress.IPv4Address | ipaddress.IPv6Address | ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw = str(os.getenv("TRUSTED_PROXY_IPS", "") or "").strip()
    networks: list[
        ipaddress.IPv4Address
        | ipaddress.IPv6Address
        | ipaddress.IPv4Network
        | ipaddress.IPv6Network
    ] = []
    if not raw:
        return networks
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            if "/" in token:
                networks.append(ipaddress.ip_network(token, strict=False))
            else:
                networks.append(ipaddress.ip_address(token))
        except ValueError:
            continue
    return networks


def _loopback_like(value: str) -> bool:
    if not value:
        return False
    if value.lower() in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _host_in_trusted_networks(value: str, networks: list[Any]) -> bool:
    if not value:
        return False
    try:
        address = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return False
    return any(
        address in network
        if isinstance(network, (ipaddress.IPv4Network, ipaddress.IPv6Network))
        else address == network
        for network in networks
    )


def _resolve_origin(request: Request) -> dict[str, object]:
    cached = getattr(request.state, "request_origin", None)
    if isinstance(cached, dict):
        return cached
    direct = _client_host(request)
    forwarded = _forwarded_for_entries(request)
    trusted_proxies = _configured_trusted_proxies()
    if not forwarded:
        # No proxy header: socket peer is authoritative. A missing peer
        # (for example a Unix-socket connection) is only possible locally.
        is_local = bool(direct) and _loopback_like(direct)
        if not direct and getattr(getattr(request, "scope", {}), "client", None) is None:
            is_local = True
        origin = {
            "ip": direct,
            "local": is_local,
            "proxied": False,
            "trusted": True,
        }
        request.state.request_origin = origin
        return origin

    if not trusted_proxies or not _host_in_trusted_networks(direct, trusted_proxies):
        # The direct peer is loopback or otherwise undeclared and a forwarded
        # header is present. The app cannot attribute the header to a proxy it
        # trusts, so it must not grant loopback privileges for this request.
        origin = {
            "ip": direct,
            "local": False,
            "proxied": True,
            "trusted": False,
        }
        request.state.request_origin = origin
        return origin

    # Trusted chain: walk from the direct peer inward and keep the first hop
    # that is not one of our trusted proxies. If every hop is trusted the
    # client itself sat on a trusted proxy/loopback path.
    hops = list(forwarded)
    hops.append(direct)
    while hops:
        candidate = hops[-1]
        if _host_in_trusted_networks(candidate, trusted_proxies) or _loopback_like(candidate):
            hops.pop()
            continue
        break
    if hops:
        real_ip = hops[-1]
    elif forwarded:
        real_ip = forwarded[0]
    else:
        real_ip = direct
    origin = {
        "ip": real_ip,
        "local": _loopback_like(real_ip),
        "proxied": True,
        "trusted": True,
    }
    request.state.request_origin = origin
    return origin


def request_client_ip(request: Request) -> str:
    """Return the most plausible real client IP for audit and rate limiting."""
    return str(_resolve_origin(request).get("ip") or "").strip()


def request_is_local_origin(request: Request) -> bool:
    """True only for a genuine loopback/Unix-socket connection or a fully trusted local chain."""
    return bool(_resolve_origin(request).get("local"))


def request_user_agent(request: Request) -> str:
    return str(request.headers.get("user-agent") or "").strip()
