"""Webhook execution helpers for the Integrator Agent."""

from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from backend.agent.agents.integrator.push import summarize_payload

_MAX_RESPONSE_BYTES = 4096
_MAX_RETRY_ATTEMPTS = 5
_MIN_WEBHOOK_TIMEOUT_SECONDS = 0.1
_MAX_WEBHOOK_TIMEOUT_SECONDS = 60.0
_WEBHOOK_URL_KEYS = ("webhook_url", "url", "endpoint")
_HMAC_SECRET_KEYS = ("hmac_secret", "signing_secret", "signature_secret", "webhook_hmac_secret")
_HMAC_HEADER_KEYS = ("hmac_header", "signature_header", "webhook_signature_header")
_HMAC_ALGORITHM_KEYS = ("hmac_algorithm", "signature_algorithm", "webhook_hmac_algorithm")
_SUPPORTED_HMAC_ALGORITHMS = {"sha1", "sha256", "sha512"}
_SECRET_KEYWORDS = (
    "secret",
    "token",
    "password",
    "credential",
    "key",
    "webhook_url",
    "url",
    "authorization",
    "auth",
)
_RETRYABLE_STATUS_CODES = {0, 408, 409, 425, 429}
_REDACTED = "***redacted***"


@dataclass(slots=True)
class WebhookExecutionResponse:
    status_code: int
    body: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: int | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status_code < 300


class WebhookClient(Protocol):
    async def post_json(
        self,
        url: str,
        payload: Any,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 10.0,
    ) -> WebhookExecutionResponse:
        """POST a JSON payload and return a summarized response."""


class UrlLibWebhookClient:
    """Small stdlib webhook client used only when execution is explicitly enabled."""

    def __init__(self, *, opener: Any | None = None) -> None:
        self._opener = opener

    async def post_json(
        self,
        url: str,
        payload: Any,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 10.0,
    ) -> WebhookExecutionResponse:
        return await asyncio.to_thread(
            self._post_json,
            url,
            payload,
            headers=dict(headers or {}),
            timeout_seconds=timeout_seconds,
        )

    def _post_json(
        self,
        url: str,
        payload: Any,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> WebhookExecutionResponse:
        started_at = time.perf_counter()
        body = encode_webhook_json_payload(payload)
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
            **headers,
        }
        request = urllib_request.Request(
            url,
            data=body,
            headers=request_headers,
            method="POST",
        )

        try:
            with self._open(request, timeout_seconds=timeout_seconds) as response:
                return WebhookExecutionResponse(
                    status_code=int(response.status),
                    body=_decode_response_body(response.read(_MAX_RESPONSE_BYTES + 1)),
                    headers={str(key): str(value) for key, value in response.headers.items()},
                    elapsed_ms=_elapsed_ms(started_at),
                )
        except HTTPError as exc:
            return WebhookExecutionResponse(
                status_code=int(exc.code),
                body=_decode_response_body(exc.read(_MAX_RESPONSE_BYTES + 1)),
                headers={str(key): str(value) for key, value in exc.headers.items()},
                elapsed_ms=_elapsed_ms(started_at),
            )
        except URLError as exc:
            return WebhookExecutionResponse(
                status_code=0,
                elapsed_ms=_elapsed_ms(started_at),
                error=str(getattr(exc, "reason", exc)),
            )
        except OSError as exc:
            return WebhookExecutionResponse(
                status_code=0,
                elapsed_ms=_elapsed_ms(started_at),
                error=str(exc),
            )

    def _open(self, request: urllib_request.Request, *, timeout_seconds: float) -> Any:
        if self._opener is not None:
            return self._opener.open(request, timeout=timeout_seconds)
        return urllib_request.urlopen(request, timeout=timeout_seconds)


class _NoRedirectHTTPRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Convert redirects into HTTPError so callers can validate 3xx targets themselves."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise HTTPError(req.full_url, code, msg, headers, fp)


class NoRedirectUrlLibWebhookClient(UrlLibWebhookClient):
    """UrlLib webhook client variant that returns 3xx responses without following them."""

    def __init__(self) -> None:
        super().__init__(
            opener=urllib_request.build_opener(_NoRedirectHTTPRedirectHandler()),
        )


def resolve_webhook_url(settings: Mapping[str, Any]) -> str:
    for key in _WEBHOOK_URL_KEYS:
        value = settings.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def validate_webhook_url(url: str) -> str:
    if not url:
        return "Webhook URL is required for real integration execution."
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        return "Webhook URL must use http or https."
    if not parsed.netloc or not parsed.hostname:
        return "Webhook URL must include a host."
    return ""


def resolve_webhook_headers(settings: Mapping[str, Any]) -> dict[str, str]:
    raw_headers = settings.get("headers")
    if not isinstance(raw_headers, Mapping):
        return {}
    headers: dict[str, str] = {}
    for key, value in raw_headers.items():
        key_text = str(key or "").strip()
        if key_text:
            headers[key_text] = str(value)
    return headers


def resolve_webhook_hmac_headers(
    settings: Mapping[str, Any],
    payload: Any,
) -> tuple[dict[str, str], dict[str, Any], str]:
    secret = _first_text(settings, _HMAC_SECRET_KEYS)
    if not secret:
        return {}, {"enabled": False}, ""

    algorithm = _normalize_hmac_algorithm(_first_text(settings, _HMAC_ALGORITHM_KEYS) or "sha256")
    if algorithm not in _SUPPORTED_HMAC_ALGORITHMS:
        return {}, {}, f"Unsupported webhook HMAC algorithm: {algorithm or 'empty'}."

    header_name = _first_text(settings, _HMAC_HEADER_KEYS) or "X-Integrator-Signature"
    body = encode_webhook_json_payload(payload)
    digest = hmac.new(secret.encode("utf-8"), body, getattr(hashlib, algorithm)).hexdigest()
    header_value = f"{algorithm}={digest}"
    return (
        {header_name: header_value},
        {
            "enabled": True,
            "algorithm": algorithm,
            "header": header_name,
            "body_sha256": hashlib.sha256(body).hexdigest()[:16],
        },
        "",
    )


def resolve_webhook_retry_attempts(settings: Mapping[str, Any], default_attempts: int = 1) -> int:
    for key in ("retry_attempts", "max_attempts", "webhook_retry_attempts"):
        if key in settings:
            return _coerce_retry_attempts(settings.get(key), default_attempts=default_attempts)
    return _coerce_retry_attempts(default_attempts, default_attempts=1)


def resolve_webhook_retry_backoff_seconds(settings: Mapping[str, Any], default_seconds: float = 0.0) -> float:
    for key in ("retry_backoff_seconds", "webhook_retry_backoff_seconds"):
        if key in settings:
            return _coerce_non_negative_float(settings.get(key), default_seconds=default_seconds)
    return _coerce_non_negative_float(default_seconds, default_seconds=0.0)


def resolve_webhook_timeout_seconds(
    settings: Mapping[str, Any],
    default_seconds: float = 10.0,
) -> tuple[float, str]:
    """Resolve and validate webhook timeout without silently accepting unsafe values."""

    value: Any = default_seconds
    for key in ("timeout_seconds", "webhook_timeout_seconds"):
        if key in settings:
            value = settings.get(key)
            break

    try:
        timeout_seconds = float(value)
    except (TypeError, ValueError):
        return 0.0, "Webhook timeout_seconds must be a number."

    if timeout_seconds < _MIN_WEBHOOK_TIMEOUT_SECONDS:
        return 0.0, "Webhook timeout_seconds must be at least 0.1 seconds."
    if timeout_seconds > _MAX_WEBHOOK_TIMEOUT_SECONDS:
        return 0.0, "Webhook timeout_seconds must be at most 60 seconds."
    return timeout_seconds, ""


async def post_webhook_with_retry(
    client: WebhookClient,
    url: str,
    payload: Any,
    *,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: float = 10.0,
    max_attempts: int = 1,
    backoff_seconds: float = 0.0,
) -> tuple[WebhookExecutionResponse, dict[str, Any]]:
    attempts_limit = _coerce_retry_attempts(max_attempts, default_attempts=1)
    wait_seconds = _coerce_non_negative_float(backoff_seconds, default_seconds=0.0)
    attempts: list[dict[str, Any]] = []
    final_response = WebhookExecutionResponse(status_code=0, error="Webhook POST did not run.")

    for attempt_number in range(1, attempts_limit + 1):
        try:
            final_response = await client.post_json(
                url,
                payload,
                headers=headers,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - defensive boundary for injected clients.
            final_response = WebhookExecutionResponse(status_code=0, error=str(exc))

        will_retry = attempt_number < attempts_limit and _is_retryable_response(final_response)
        attempts.append(_summarize_webhook_attempt(final_response, attempt_number, will_retry=will_retry))
        if final_response.ok or not will_retry:
            break
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    return final_response, _build_retry_summary(attempts_limit, attempts)


def endpoint_info(url: str) -> dict[str, Any]:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    port = parsed.port
    path = parsed.path or "/"
    target = f"{scheme}://{parsed.netloc.lower()}{path}"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    info: dict[str, Any] = {
        "scheme": scheme,
        "host": host,
        "fingerprint": hashlib.sha256(target.encode("utf-8")).hexdigest()[:16],
    }
    if port is not None:
        info["port"] = port
    return info


def build_webhook_execution_artifact(
    *,
    task_id: str,
    action: str,
    connector: dict[str, Any],
    endpoint: dict[str, Any],
    payload: Any,
    request: str,
    response: WebhookExecutionResponse,
    retry_summary: Mapping[str, Any] | None = None,
    signing_summary: Mapping[str, Any] | None = None,
    secret_values: Iterable[str] = (),
) -> dict[str, Any]:
    status = "succeeded" if response.ok else "failed"
    content = {
        "operation_id": f"{task_id or 'integration'}:{action}:execute",
        "action": action,
        "dry_run": False,
        "executed": True,
        "status": status,
        "connector": connector,
        "endpoint": endpoint,
        "request": request,
        "payload_summary": summarize_payload(payload),
        "response": summarize_webhook_response(response, secret_values=secret_values),
    }
    if retry_summary is not None:
        content["retry"] = dict(retry_summary)
    if signing_summary is not None:
        content["signing"] = dict(signing_summary)
    return {
        "type": "integration_execution",
        "title": "Integration webhook execution",
        "content": content,
    }


def build_webhook_outbound_audit_artifact(
    *,
    task_id: str,
    action: str,
    connector: dict[str, Any],
    endpoint: dict[str, Any],
    payload: Any,
    response: WebhookExecutionResponse,
    retry_summary: Mapping[str, Any] | None = None,
    signing_summary: Mapping[str, Any] | None = None,
    secret_values: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "type": "integration_outbound_audit",
        "title": "Integration outbound audit",
        "content": build_webhook_outbound_audit_record(
            task_id=task_id,
            action=action,
            connector=connector,
            endpoint=endpoint,
            payload=payload,
            response=response,
            retry_summary=retry_summary,
            signing_summary=signing_summary,
            secret_values=secret_values,
        ),
    }


def build_webhook_outbound_audit_record(
    *,
    task_id: str,
    action: str,
    connector: dict[str, Any],
    endpoint: dict[str, Any],
    payload: Any,
    response: WebhookExecutionResponse,
    retry_summary: Mapping[str, Any] | None = None,
    signing_summary: Mapping[str, Any] | None = None,
    secret_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a secret-safe record for external webhook execution audit logs."""
    record: dict[str, Any] = {
        "event": "integrator.webhook.outbound",
        "task_id": task_id,
        "action": action,
        "dry_run": False,
        "executed": True,
        "status": "succeeded" if response.ok else "failed",
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "connector": {
            "id": str(connector.get("id") or ""),
            "type": str(connector.get("type") or ""),
            "name": str(connector.get("name") or ""),
            "approved": bool(connector.get("approved")),
        },
        "endpoint": dict(endpoint),
        "payload_summary": summarize_payload(payload),
        "response": summarize_webhook_response(response, secret_values=secret_values),
    }
    if retry_summary is not None:
        record["retry"] = dict(retry_summary)
    if signing_summary is not None:
        record["signing"] = dict(signing_summary)
    return record


def summarize_webhook_response(
    response: WebhookExecutionResponse,
    *,
    secret_values: Iterable[str] = (),
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": response.ok,
        "status_code": response.status_code,
    }
    if response.elapsed_ms is not None:
        summary["elapsed_ms"] = response.elapsed_ms
    content_type = _header_value(response.headers, "content-type")
    if content_type:
        summary["content_type"] = content_type
    body_preview = response.body.strip()
    if body_preview:
        summary["body_preview"] = redact_secret_values(body_preview[:500], secret_values)
    if response.error:
        summary["error"] = redact_secret_values(response.error, secret_values)
    return summary


def collect_webhook_secret_values(settings: Mapping[str, Any]) -> tuple[str, ...]:
    secrets: list[str] = []

    def visit(value: Any, *, key: str = "") -> None:
        key_is_secret = _is_secret_key(key)
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                visit(child_value, key=str(child_key))
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item, key=key if key_is_secret else "")
            return
        if key_is_secret:
            text = str(value or "").strip()
            if text:
                secrets.append(text)

    visit(settings)
    return tuple(dict.fromkeys(secrets))


def redact_secret_values(text: str, secret_values: Iterable[str]) -> str:
    safe_text = str(text or "")
    for secret in sorted({str(value) for value in secret_values if str(value or "").strip()}, key=len, reverse=True):
        # Avoid replacing common short words while still redacting real tokens,
        # URLs, and Authorization header values echoed by a failing client.
        if len(secret) >= 4:
            safe_text = safe_text.replace(secret, _REDACTED)
    return safe_text


def encode_webhook_json_payload(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _decode_response_body(data: bytes) -> str:
    truncated = len(data) > _MAX_RESPONSE_BYTES
    text = data[:_MAX_RESPONSE_BYTES].decode("utf-8", errors="replace")
    return f"{text}...[truncated]" if truncated else text


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _header_value(headers: Mapping[str, str], name: str) -> str:
    normalized = name.lower()
    for key, value in headers.items():
        if str(key).lower() == normalized:
            return str(value)
    return ""


def _is_retryable_response(response: WebhookExecutionResponse) -> bool:
    if response.ok:
        return False
    if response.error:
        return True
    return response.status_code in _RETRYABLE_STATUS_CODES or 500 <= response.status_code <= 599


def _summarize_webhook_attempt(
    response: WebhookExecutionResponse,
    attempt_number: int,
    *,
    will_retry: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "attempt": attempt_number,
        "ok": response.ok,
        "status_code": response.status_code,
        "will_retry": will_retry,
    }
    if response.elapsed_ms is not None:
        summary["elapsed_ms"] = response.elapsed_ms
    if response.error:
        summary["error_present"] = True
    return summary


def _build_retry_summary(max_attempts: int, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    final_attempt = attempts[-1] if attempts else {}
    return {
        "max_attempts": max_attempts,
        "attempted": len(attempts),
        "exhausted": bool(attempts and not final_attempt.get("ok") and len(attempts) >= max_attempts),
        "final_status_code": int(final_attempt.get("status_code") or 0),
        "attempts": attempts,
    }


def _coerce_retry_attempts(value: Any, *, default_attempts: int) -> int:
    try:
        attempts = int(value)
    except (TypeError, ValueError):
        attempts = int(default_attempts)
    return max(1, min(attempts, _MAX_RETRY_ATTEMPTS))


def _coerce_non_negative_float(value: Any, *, default_seconds: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default_seconds)
    return max(0.0, number)


def _is_secret_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    return bool(normalized) and any(keyword in normalized for keyword in _SECRET_KEYWORDS)


def _first_text(settings: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = settings.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_hmac_algorithm(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "")


__all__ = [
    "NoRedirectUrlLibWebhookClient",
    "UrlLibWebhookClient",
    "WebhookClient",
    "WebhookExecutionResponse",
    "build_webhook_execution_artifact",
    "build_webhook_outbound_audit_artifact",
    "build_webhook_outbound_audit_record",
    "collect_webhook_secret_values",
    "encode_webhook_json_payload",
    "endpoint_info",
    "post_webhook_with_retry",
    "redact_secret_values",
    "resolve_webhook_hmac_headers",
    "resolve_webhook_headers",
    "resolve_webhook_retry_attempts",
    "resolve_webhook_retry_backoff_seconds",
    "resolve_webhook_timeout_seconds",
    "resolve_webhook_url",
    "summarize_webhook_response",
    "validate_webhook_url",
]
