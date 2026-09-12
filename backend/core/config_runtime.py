"""Runtime configuration and secret helpers for the API server."""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

import httpx
from fastapi import HTTPException

from backend.core.outbound_http import (
    OutboundURLBlockedError,
    base_urls_match,
    normalize_base_url,
)

_CLOUD_MODEL_API_KEY_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,127}$")
_BOUND_CLOUD_MODEL_API_KEY_PREFIX = "bound:v1:"


def stored_config_value(store: Any, logger: Any, key: str, default: str = "") -> str:
    try:
        return str(store.get_value(key, default))
    except Exception:
        logger.exception("Failed to read persisted app config key=%s", key)
        return str(default or "")


def sync_runtime_secret_from_store(
    store: Any,
    logger: Any,
    env_name: str,
    config_key: str,
) -> str:
    persisted_value = stored_config_value(store, logger, config_key, "")
    if persisted_value:
        os.environ[env_name] = persisted_value
        return persisted_value
    return str(os.getenv(env_name) or "").strip()


def normalize_cloud_model_api_key_ref(value: Any, *, allow_empty: bool = False) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        if allow_empty:
            return ""
        raise HTTPException(
            status_code=400, detail="Cloud model API key ref 不能为空。"
        )
    if not _CLOUD_MODEL_API_KEY_REF_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=400, detail="Cloud model API key ref 格式无效。"
        )
    return normalized


def cloud_model_api_key_config_key(api_key_ref: str) -> str:
    normalized_ref = normalize_cloud_model_api_key_ref(api_key_ref)
    return f"cloud_model_api_key:{normalized_ref}"


def _bound_cloud_model_api_key_value(*, api_key: str, base_url: str) -> str:
    return _BOUND_CLOUD_MODEL_API_KEY_PREFIX + json.dumps(
        {
            "api_key": api_key,
            "base_url": base_url,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _parse_cloud_model_api_key_value(value: str) -> tuple[str, str]:
    normalized = str(value or "")
    if not normalized.startswith(_BOUND_CLOUD_MODEL_API_KEY_PREFIX):
        return normalized, ""
    try:
        payload = json.loads(normalized[len(_BOUND_CLOUD_MODEL_API_KEY_PREFIX) :])
    except (TypeError, ValueError) as exc:
        raise ValueError("Stored cloud model API key binding is invalid.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Stored cloud model API key binding is invalid.")
    api_key = str(payload.get("api_key") or "").strip()
    base_url = str(payload.get("base_url") or "").strip()
    if not api_key or not base_url:
        raise ValueError("Stored cloud model API key binding is invalid.")
    return api_key, base_url


def upsert_cloud_model_api_key(
    store: Any,
    api_key_ref: str | None,
    api_key: str,
    base_url: str,
) -> str:
    normalized_api_key = str(api_key or "").strip()
    if not normalized_api_key:
        raise HTTPException(status_code=400, detail="Cloud model API Key 不能为空。")
    try:
        normalized_base_url = normalize_base_url(base_url)
    except OutboundURLBlockedError as exc:
        raise HTTPException(status_code=400, detail="Cloud model base_url 格式无效。") from exc

    normalized_ref = (
        normalize_cloud_model_api_key_ref(api_key_ref, allow_empty=True)
        if api_key_ref is not None
        else ""
    )
    if not normalized_ref:
        normalized_ref = f"cmk-{uuid.uuid4().hex}"

    store.set(
        cloud_model_api_key_config_key(normalized_ref),
        _bound_cloud_model_api_key_value(
            api_key=normalized_api_key,
            base_url=normalized_base_url,
        ),
    )
    return normalized_ref


def delete_cloud_model_api_key(store: Any, api_key_ref: str) -> bool:
    return bool(store.delete(cloud_model_api_key_config_key(api_key_ref)))


def resolve_model_api_key(
    store: Any,
    logger: Any,
    model_config: Any,
    *,
    model_config_payload: Any,
    trusted_base_url: str,
) -> str:
    data = model_config_payload(model_config)
    direct_api_key = str(data.get("api_key") or "").strip()
    if direct_api_key:
        return direct_api_key

    api_key_ref = str(data.get("api_key_ref") or "").strip()
    if not api_key_ref:
        return ""

    stored_value = stored_config_value(
        store,
        logger,
        cloud_model_api_key_config_key(api_key_ref),
        "",
    )
    if not stored_value:
        return ""
    resolved_api_key, bound_base_url = _parse_cloud_model_api_key_value(stored_value)
    requested_base_url = str(data.get("base_url") or trusted_base_url or "").strip()
    if bound_base_url:
        if not base_urls_match(requested_base_url, bound_base_url):
            raise ValueError(
                "Cloud model API key ref is bound to a different base_url."
            )
        return resolved_api_key

    # Legacy refs did not persist endpoint provenance. Keep them usable only
    # with the administrator-configured provider URL.
    if not base_urls_match(requested_base_url, trusted_base_url):
        raise ValueError(
            "Legacy cloud model API key refs may only use the configured provider base_url."
        )
    return resolved_api_key


async def validate_tavily_api_key(api_key: str) -> None:
    normalized_key = str(api_key or "").strip()
    if not normalized_key:
        raise HTTPException(status_code=400, detail="Tavily API Key 不能为空。")

    payload = {
        "api_key": normalized_key,
        "query": "OpenAI",
        "max_results": 1,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=502, detail="Tavily API Key 校验超时，请稍后重试。"
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Tavily API Key 校验失败，无法连接 Tavily：{exc}",
        ) from exc

    if response.status_code == 401:
        raise HTTPException(status_code=400, detail="Tavily API Key 无效，保存失败。")
    if response.status_code >= 400:
        detail = response.text.strip() or f"HTTP {response.status_code}"
        raise HTTPException(
            status_code=502,
            detail=f"Tavily API Key 校验失败：{detail}",
        )
