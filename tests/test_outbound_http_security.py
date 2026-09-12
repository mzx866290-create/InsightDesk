import asyncio
import gzip

import httpx
import pytest

from backend.agent.providers import ollama as ollama_provider
from backend.core import outbound_http as outbound_http_module
from backend.core.outbound_http import (
    OutboundRedirectError,
    OutboundRequestTimeoutError,
    OutboundResponseTooLargeError,
    OutboundURLBlockedError,
    request_public_url,
    request_trusted_url,
    validate_public_outbound_url,
)
from search_runtime import service as search_service
from search_runtime.types import (
    SearchProviderHTTPError,
    SearchRuntimeError,
    SearchTimeoutError,
)

PUBLIC_TEST_IP = "93.184.216.34"


async def _unexpected_resolver(_hostname: str, _port: int) -> tuple[str, ...]:
    raise AssertionError("literal and explicitly blocked hosts must not reach DNS")


def _resolver_for(*addresses: str):
    async def resolve(_hostname: str, _port: int) -> tuple[str, ...]:
        return tuple(addresses)

    return resolve


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/admin",
        "http://[fc00::1]/admin",
        "http://[fe80::1]/admin",
        "http://metadata.google.internal/computeMetadata/v1/",
    ],
)
def test_validate_public_outbound_url_blocks_local_private_and_metadata_targets(url):
    with pytest.raises(OutboundURLBlockedError):
        asyncio.run(
            validate_public_outbound_url(
                url,
                resolver=_unexpected_resolver,
            )
        )


@pytest.mark.parametrize(
    "addresses",
    [
        ("192.168.1.20",),
        (PUBLIC_TEST_IP, "10.0.0.5"),
    ],
)
def test_validate_public_outbound_url_rejects_dns_sets_containing_non_public_ip(addresses):
    with pytest.raises(OutboundURLBlockedError):
        asyncio.run(
            validate_public_outbound_url(
                "https://public.example/resource",
                resolver=_resolver_for(*addresses),
            )
        )


def test_validate_public_outbound_url_accepts_public_dns_result():
    validated = asyncio.run(
        validate_public_outbound_url(
            "https://public.example/resource#fragment",
            resolver=_resolver_for(PUBLIC_TEST_IP),
        )
    )

    assert validated == "https://public.example/resource"


def test_safe_network_backend_connects_to_validated_ip_instead_of_hostname():
    captured: dict[str, object] = {}
    sentinel_stream = object()

    class RecordingNetworkBackend:
        async def connect_tcp(
            self,
            host,
            port,
            timeout=None,
            local_address=None,
            socket_options=None,
        ):
            captured.update(
                {
                    "host": host,
                    "port": port,
                    "timeout": timeout,
                    "local_address": local_address,
                    "socket_options": socket_options,
                }
            )
            return sentinel_stream

    guarded_backend = outbound_http_module._PublicOnlyAsyncNetworkBackend(
        resolver=_resolver_for(PUBLIC_TEST_IP),
        backend=RecordingNetworkBackend(),
    )

    stream = asyncio.run(
        guarded_backend.connect_tcp(
            "public.example",
            443,
            timeout=2.0,
            local_address=None,
            socket_options=None,
        )
    )

    assert stream is sentinel_stream
    assert captured["host"] == PUBLIC_TEST_IP
    assert captured["port"] == 443


def test_request_public_url_revalidates_redirect_before_sending_next_hop():
    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/private"},
        )

    with pytest.raises(OutboundURLBlockedError):
        asyncio.run(
            request_public_url(
                "https://public.example/start",
                timeout_seconds=1.0,
                resolver=_resolver_for(PUBLIC_TEST_IP),
                transport=httpx.MockTransport(handler),
            )
        )

    assert requested_urls == ["https://public.example/start"]


def test_request_public_url_rejects_response_over_decompressed_byte_limit():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 11)

    with pytest.raises(OutboundResponseTooLargeError):
        asyncio.run(
            request_public_url(
                "https://public.example/content",
                timeout_seconds=1.0,
                max_response_bytes=10,
                resolver=_resolver_for(PUBLIC_TEST_IP),
                transport=httpx.MockTransport(handler),
            )
        )


def test_request_public_url_limits_gzip_body_by_decompressed_size():
    compressed_body = gzip.compress(b"x" * 1024)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=httpx.ByteStream(compressed_body),
        )

    assert len(compressed_body) < 100
    with pytest.raises(OutboundResponseTooLargeError):
        asyncio.run(
            request_public_url(
                "https://public.example/compressed-large",
                timeout_seconds=1.0,
                max_response_bytes=100,
                resolver=_resolver_for(PUBLIC_TEST_IP),
                transport=httpx.MockTransport(handler),
            )
        )


def test_request_public_url_returns_compressed_response_after_single_decode():
    decoded_body = b"compressed payload"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=httpx.ByteStream(gzip.compress(decoded_body)),
        )

    response = asyncio.run(
        request_public_url(
            "https://public.example/compressed",
            timeout_seconds=1.0,
            resolver=_resolver_for(PUBLIC_TEST_IP),
            transport=httpx.MockTransport(handler),
        )
    )

    assert response.content == decoded_body
    assert "content-encoding" not in response.headers


def test_request_public_url_enforces_total_timeout_while_reading_body():
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.05)
            yield b"ok"

        async def aclose(self) -> None:
            return None

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=SlowStream())

    with pytest.raises(OutboundRequestTimeoutError):
        asyncio.run(
            request_public_url(
                "https://public.example/slow",
                timeout_seconds=0.001,
                resolver=_resolver_for(PUBLIC_TEST_IP),
                transport=httpx.MockTransport(handler),
            )
        )


def test_request_trusted_url_disables_redirects():
    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1:11435/api/tags"},
        )

    with pytest.raises(OutboundRedirectError):
        asyncio.run(
            request_trusted_url(
                "http://127.0.0.1:11434/api/tags",
                timeout_seconds=1.0,
                transport=httpx.MockTransport(handler),
            )
        )

    assert requested_urls == ["http://127.0.0.1:11434/api/tags"]


def test_ollama_model_listing_blocks_nonconfigured_private_target(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def fail_trusted_request(*_args, **_kwargs):
        raise AssertionError("nonconfigured private targets must not use the trusted path")

    monkeypatch.setattr(ollama_provider, "request_trusted_url", fail_trusted_request)

    payload = asyncio.run(
        ollama_provider.list_ollama_models("http://192.168.10.20:11434")
    )

    assert payload["models"] == []
    assert "error" in payload


def test_fetch_webpage_maps_blocked_url_to_sanitized_search_error(monkeypatch):
    async def blocked_request(*_args, **_kwargs):
        raise OutboundURLBlockedError("sensitive resolver detail: 10.0.0.8")

    monkeypatch.setattr(search_service, "request_public_url", blocked_request)

    with pytest.raises(SearchRuntimeError) as exc_info:
        asyncio.run(search_service.fetch_webpage_document("https://blocked.example/internal"))

    assert str(exc_info.value) == "抓取网页失败: 目标地址不允许访问"
    assert "10.0.0.8" not in str(exc_info.value)


def test_fetch_webpage_maps_total_timeout_to_search_timeout(monkeypatch):
    async def timed_out_request(*_args, **_kwargs):
        raise OutboundRequestTimeoutError("internal timeout detail")

    monkeypatch.setattr(search_service, "request_public_url", timed_out_request)

    with pytest.raises(SearchTimeoutError, match="网页请求超时"):
        asyncio.run(search_service.fetch_webpage_document("https://public.example/slow"))


def test_fetch_webpage_truncates_http_error_response_text(monkeypatch):
    response_body = "x" * 2500

    async def failed_request(*_args, **_kwargs):
        request = httpx.Request("GET", "https://public.example/error")
        return httpx.Response(503, content=response_body, request=request)

    monkeypatch.setattr(search_service, "request_public_url", failed_request)

    with pytest.raises(SearchProviderHTTPError) as exc_info:
        asyncio.run(search_service.fetch_webpage_document("https://public.example/error"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.response_text == response_body[:2000]
