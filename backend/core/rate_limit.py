"""Simple in-memory per-client rate limiter for expensive API endpoints.

The middleware is registered conditionally from the API server so local-only
deployments and the test suite keep their default behavior. Enable it with
``GENERAL_RATE_LIMIT_ENABLED=true``; thresholds are configurable through
``GENERAL_RATE_LIMIT_RPM`` and ``GENERAL_RATE_LIMIT_BURST``.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.core.request_runtime import request_client_ip

_DISABLED_VALUES = {"0", "false", "off", "no", "disabled"}


@dataclass
class _BucketState:
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)


class RateLimiter:
    """Token-bucket rate limiter keyed by the resolved real client IP."""

    def __init__(self, requests_per_minute: int = 60, burst: int = 15):
        normalized_rate = max(1, int(requests_per_minute or 60))
        normalized_burst = max(1, int(burst or 1))
        self._rate = normalized_rate / 60.0
        self._burst = normalized_burst
        self._buckets: dict[str, _BucketState] = defaultdict(
            lambda: _BucketState(tokens=normalized_burst, last_refill=time.monotonic())
        )
        self._lock = threading.Lock()

    def _client_key(self, request: Request) -> str:
        return request_client_ip(request) or "unknown"

    def allow(self, request: Request) -> bool:
        key = self._client_key(request)
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self._burst, bucket.tokens + elapsed * self._rate)
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True
            return False


_EXPENSIVE_PATH_PREFIXES = (
    "/api/chat",
    "/api/research",
    "/api/tasks/run",
    "/api/documents/upload",
    "/api/knowledge-bases/rebuild",
)

_global_limiter = RateLimiter(requests_per_minute=60, burst=15)


def general_rate_limit_enabled() -> bool:
    raw = str(os.getenv("GENERAL_RATE_LIMIT_ENABLED") or "").strip().lower()
    return bool(raw) and raw not in _DISABLED_VALUES


def general_rate_limit_limits() -> tuple[int, int]:
    def positive_env(name: str, default: int) -> int:
        raw = str(os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            return max(1, int(raw))
        except ValueError:
            return default

    return (
        positive_env("GENERAL_RATE_LIMIT_RPM", 60),
        positive_env("GENERAL_RATE_LIMIT_BURST", 15),
    )


def rate_limit_middleware_factory(
    limiter: RateLimiter | None = None,
):
    """Return a FastAPI middleware that rate-limits expensive endpoints."""
    active_limiter = limiter or _global_limiter

    async def rate_limit_middleware(request: Request, call_next: Any):
        path = request.url.path
        if request.method in ("POST", "PUT") and any(
            path.startswith(prefix) for prefix in _EXPENSIVE_PATH_PREFIXES
        ) and not active_limiter.allow(request):
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMIT",
                    "message": "Too many requests. Please slow down.",
                    "suggestion": "Wait a moment before retrying.",
                },
                headers={"Retry-After": "5"},
            )
        return await call_next(request)

    return rate_limit_middleware
