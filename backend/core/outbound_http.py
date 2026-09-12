"""SSRF-safe helpers for small outbound HTTP GET requests.

The guard validates every redirect target, resolves DNS before connecting, and
pins the connection to the validated public IP address.  This avoids the common
"validate hostname, then resolve again" DNS-rebinding gap.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

import httpcore
import httpx

DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_OUTBOUND_URL_LENGTH = 8192
_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_BLOCKED_HOSTNAMES = {
    "instance-data",
    "instance-data.ec2.internal",
    "metadata",
    "metadata.azure.internal",
    "metadata.google.internal",
    "metadata.oraclecloud.com",
}
_BLOCKED_HOST_SUFFIXES = (
    ".cluster.local",
    ".internal",
    ".lan",
    ".local",
    ".localdomain",
    ".localhost",
    ".svc",
)

DNSResolver = Callable[[str, int], Awaitable[Sequence[str]]]


class OutboundRequestError(RuntimeError):
    """Base error for rejected or bounded outbound requests."""


class OutboundURLBlockedError(OutboundRequestError):
    """Raised when an outbound URL or resolved address is not public."""


class OutboundResponseTooLargeError(OutboundRequestError):
    """Raised when a response exceeds the configured byte limit."""


class OutboundRedirectError(OutboundRequestError):
    """Raised when an outbound request exceeds its redirect budget."""


class OutboundRequestTimeoutError(OutboundRequestError):
    """Raised when the complete outbound operation exceeds its timeout."""


def _normalized_hostname(hostname: str) -> str:
    normalized = str(hostname or "").strip().rstrip(".").lower()
    if not normalized:
        raise OutboundURLBlockedError("Outbound URL must include a hostname.")
    if "%" in normalized:
        raise OutboundURLBlockedError("Scoped or percent-encoded hosts are not allowed.")
    try:
        return normalized.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise OutboundURLBlockedError("Outbound URL hostname is invalid.") from exc


def _parse_http_url(url: str, *, require_base_url: bool = False) -> tuple[SplitResult, str, int]:
    raw_url = str(url or "").strip()
    if not raw_url:
        raise OutboundURLBlockedError("Outbound URL is required.")
    if len(raw_url) > MAX_OUTBOUND_URL_LENGTH:
        raise OutboundURLBlockedError("Outbound URL is too long.")
    if "\\" in raw_url or any(ord(char) < 32 or ord(char) == 127 for char in raw_url):
        raise OutboundURLBlockedError("Outbound URL contains unsafe characters.")

    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError as exc:
        raise OutboundURLBlockedError("Outbound URL is malformed.") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise OutboundURLBlockedError("Outbound URL must use http or https.")
    if parsed.username is not None or parsed.password is not None:
        raise OutboundURLBlockedError("Outbound URL must not include user information.")
    if require_base_url and (parsed.query or parsed.fragment):
        raise OutboundURLBlockedError("Base URL must not include a query or fragment.")

    hostname = _normalized_hostname(parsed.hostname or "")
    resolved_port = int(port or (443 if scheme == "https" else 80))
    if resolved_port < 1 or resolved_port > 65535:
        raise OutboundURLBlockedError("Outbound URL port is invalid.")
    return parsed, hostname, resolved_port


def _blocked_hostname(hostname: str) -> bool:
    return (
        hostname == "localhost"
        or hostname in _BLOCKED_HOSTNAMES
        or any(hostname.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES)
    )


def _require_public_ip(address: str) -> str:
    try:
        parsed = ipaddress.ip_address(str(address or "").strip())
    except ValueError as exc:
        raise OutboundURLBlockedError("DNS returned an invalid IP address.") from exc
    if not parsed.is_global:
        raise OutboundURLBlockedError(
            "Outbound URL resolved to a loopback, private, link-local, or reserved address."
        )
    return str(parsed)


async def _system_resolver(hostname: str, port: int) -> tuple[str, ...]:
    try:
        address_info = await asyncio.get_running_loop().getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise OutboundURLBlockedError("Outbound URL hostname could not be resolved.") from exc

    addresses = tuple(
        dict.fromkeys(
            str(sockaddr[0])
            for family, _socktype, _proto, _canonname, sockaddr in address_info
            if family in {socket.AF_INET, socket.AF_INET6} and sockaddr
        )
    )
    if not addresses:
        raise OutboundURLBlockedError("Outbound URL hostname has no IP addresses.")
    return addresses


async def resolve_public_ip_addresses(
    hostname: str,
    port: int,
    *,
    resolver: DNSResolver | None = None,
) -> tuple[str, ...]:
    """Resolve a host and reject the entire result if any address is non-public."""

    normalized_host = _normalized_hostname(hostname)
    if _blocked_hostname(normalized_host):
        raise OutboundURLBlockedError("Outbound URL targets a blocked local or metadata host.")

    try:
        literal_ip = ipaddress.ip_address(normalized_host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        return (_require_public_ip(str(literal_ip)),)

    resolved = await (resolver or _system_resolver)(normalized_host, int(port))
    addresses = tuple(dict.fromkeys(_require_public_ip(item) for item in resolved))
    if not addresses:
        raise OutboundURLBlockedError("Outbound URL hostname has no public IP addresses.")
    return addresses


async def validate_public_outbound_url(
    url: str,
    *,
    resolver: DNSResolver | None = None,
) -> str:
    """Validate URL structure and ensure all DNS results are globally routable."""

    parsed, hostname, port = _parse_http_url(url)
    await resolve_public_ip_addresses(hostname, port, resolver=resolver)
    # Fragments are client-side only; remove them before the request to avoid
    # parser ambiguity when callers append paths to user-provided values.
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))


def append_url_path(base_url: str, path: str) -> str:
    """Append a fixed path to a validated HTTP base URL without query tricks."""

    parsed, _hostname, _port = _parse_http_url(base_url, require_base_url=True)
    suffix = "/" + str(path or "").strip().lstrip("/")
    joined_path = f"{parsed.path.rstrip('/')}{suffix}" or suffix
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, joined_path, "", ""))


def _canonical_base_url(url: str) -> tuple[str, str, int, str]:
    parsed, hostname, port = _parse_http_url(url, require_base_url=True)
    path = parsed.path.rstrip("/") or "/"
    return parsed.scheme.lower(), hostname, port, path


def normalize_base_url(url: str) -> str:
    """Return a stable HTTP base URL for persistence and exact comparison."""

    scheme, hostname, port, path = _canonical_base_url(url)
    normalized_host = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    netloc = normalized_host if port == default_port else f"{normalized_host}:{port}"
    return urlunsplit((scheme, netloc, path, "", ""))


def base_urls_match(candidate: str, trusted: str) -> bool:
    """Compare HTTP base URLs after normalizing host, default port, and slash."""

    try:
        return _canonical_base_url(candidate) == _canonical_base_url(trusted)
    except OutboundURLBlockedError:
        return False


def require_matching_base_url(candidate: str, trusted: str, *, message: str) -> None:
    if not base_urls_match(candidate, trusted):
        raise ValueError(message)


def _cached_resolver(resolver: DNSResolver | None) -> DNSResolver:
    active_resolver = resolver or _system_resolver
    cache: dict[tuple[str, int], tuple[str, ...]] = {}

    async def resolve(hostname: str, port: int) -> tuple[str, ...]:
        key = (_normalized_hostname(hostname), int(port))
        if key not in cache:
            cache[key] = tuple(await active_resolver(*key))
        return cache[key]

    return resolve


class _PublicOnlyAsyncNetworkBackend(httpcore.AsyncNetworkBackend):
    """Connect to the exact public IPs returned by the validated DNS lookup."""

    def __init__(
        self,
        *,
        resolver: DNSResolver,
        backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self._resolver = resolver
        self._backend = backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await resolve_public_ip_addresses(
            host,
            port,
            resolver=self._resolver,
        )
        last_error: Exception | None = None
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # pragma: no cover - depends on live network ordering.
                last_error = exc
        if last_error is not None:
            raise last_error
        raise OutboundURLBlockedError("Outbound URL hostname has no connectable public IPs.")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        del path, timeout, socket_options
        raise OutboundURLBlockedError("Unix socket outbound requests are not allowed.")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


async def _buffer_bounded_response(
    response: httpx.Response,
    *,
    byte_limit: int,
) -> httpx.Response:
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            declared_length = 0
        if declared_length > byte_limit:
            raise OutboundResponseTooLargeError(
                f"Outbound response exceeds {byte_limit} bytes."
            )

    content = bytearray()
    async for chunk in response.aiter_bytes():
        if len(content) + len(chunk) > byte_limit:
            raise OutboundResponseTooLargeError(
                f"Outbound response exceeds {byte_limit} bytes."
            )
        content.extend(chunk)

    # ``aiter_bytes`` has already applied content decoding. Drop transport
    # headers that would make the detached response decode the body again.
    response_headers = httpx.Headers(response.headers)
    for header_name in (
        "content-encoding",
        "content-length",
        "transfer-encoding",
    ):
        response_headers.pop(header_name, None)

    return httpx.Response(
        status_code=response.status_code,
        headers=response_headers,
        content=bytes(content),
        request=response.request,
    )


def build_public_http_transport(*, resolver: DNSResolver) -> httpx.AsyncHTTPTransport:
    """Build an HTTPX transport that pins connections to validated public IPs."""

    transport = httpx.AsyncHTTPTransport(trust_env=False, retries=0)
    pool = getattr(transport, "_pool", None)
    if pool is None or not hasattr(pool, "_network_backend"):
        raise OutboundRequestError(
            "Installed httpx/httpcore does not support the SSRF-safe transport."
        )
    pool._network_backend = _PublicOnlyAsyncNetworkBackend(resolver=resolver)
    return transport


async def request_public_url(
    url: str,
    *,
    timeout_seconds: float,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    headers: Mapping[str, str] | None = None,
    resolver: DNSResolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.Response:
    """GET a public URL with bounded redirects, time, and decompressed bytes."""

    timeout_value = float(timeout_seconds)
    byte_limit = int(max_response_bytes)
    redirect_limit = int(max_redirects)
    if timeout_value <= 0:
        raise ValueError("timeout_seconds must be positive")
    if byte_limit <= 0:
        raise ValueError("max_response_bytes must be positive")
    if redirect_limit < 0:
        raise ValueError("max_redirects must be non-negative")

    resolve_once = _cached_resolver(resolver)
    active_transport = transport or build_public_http_transport(resolver=resolve_once)
    current_url = str(url or "").strip()
    redirect_count = 0

    try:
        async with asyncio.timeout(timeout_value):
            async with httpx.AsyncClient(
                transport=active_transport,
                timeout=httpx.Timeout(timeout_value),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                while True:
                    current_url = await validate_public_outbound_url(
                        current_url,
                        resolver=resolve_once,
                    )
                    async with client.stream("GET", current_url, headers=headers) as response:
                        location = response.headers.get("location")
                        if response.status_code in _REDIRECT_STATUS_CODES and location:
                            if redirect_count >= redirect_limit:
                                raise OutboundRedirectError(
                                    f"Outbound request exceeded {redirect_limit} redirects."
                                )
                            redirect_count += 1
                            current_url = urljoin(str(response.request.url), location)
                            continue

                        return await _buffer_bounded_response(
                            response,
                            byte_limit=byte_limit,
                        )
    except OutboundRequestError:
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise OutboundRequestTimeoutError(
            f"Outbound request exceeded {timeout_value:g} seconds."
        ) from exc


async def request_trusted_url(
    url: str,
    *,
    timeout_seconds: float,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    headers: Mapping[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.Response:
    """GET an administrator-trusted URL without proxying or redirects."""

    timeout_value = float(timeout_seconds)
    byte_limit = int(max_response_bytes)
    if timeout_value <= 0:
        raise ValueError("timeout_seconds must be positive")
    if byte_limit <= 0:
        raise ValueError("max_response_bytes must be positive")

    parsed, _hostname, _port = _parse_http_url(url)
    normalized_url = urlunsplit(
        (parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, "")
    )
    active_transport = transport or httpx.AsyncHTTPTransport(
        trust_env=False,
        retries=0,
    )

    try:
        async with asyncio.timeout(timeout_value):
            async with httpx.AsyncClient(
                transport=active_transport,
                timeout=httpx.Timeout(timeout_value),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream("GET", normalized_url, headers=headers) as response:
                    if (
                        response.status_code in _REDIRECT_STATUS_CODES
                        and response.headers.get("location")
                    ):
                        raise OutboundRedirectError(
                            "Redirects are not allowed for trusted outbound requests."
                        )
                    return await _buffer_bounded_response(
                        response,
                        byte_limit=byte_limit,
                    )
    except OutboundRequestError:
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise OutboundRequestTimeoutError(
            f"Outbound request exceeded {timeout_value:g} seconds."
        ) from exc


__all__ = [
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DNSResolver",
    "OutboundRedirectError",
    "OutboundRequestError",
    "OutboundRequestTimeoutError",
    "OutboundResponseTooLargeError",
    "OutboundURLBlockedError",
    "append_url_path",
    "base_urls_match",
    "build_public_http_transport",
    "normalize_base_url",
    "request_public_url",
    "request_trusted_url",
    "require_matching_base_url",
    "resolve_public_ip_addresses",
    "validate_public_outbound_url",
]
