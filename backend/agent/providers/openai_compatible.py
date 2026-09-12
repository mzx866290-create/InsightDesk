"""OpenAI-compatible LLM provider implementation."""

from __future__ import annotations

import logging
import os

from pydantic import SecretStr

from backend.core.outbound_http import base_urls_match

logger = logging.getLogger(__name__)


def _resolve_api_key(*, base_url: str, api_key: str | None) -> str:
    explicit_api_key = str(api_key or "").strip()
    if explicit_api_key:
        return explicit_api_key

    generic_base_url = str(os.getenv("OPENAI_COMPAT_BASE_URL") or "").strip()
    candidates = (
        (
            str(os.getenv("OPENAI_COMPAT_API_KEY") or "").strip(),
            generic_base_url,
        ),
        (
            str(os.getenv("OPENAI_API_KEY") or "").strip(),
            str(os.getenv("OPENAI_BASE_URL") or "").strip()
            or "https://api.openai.com/v1",
        ),
        (
            str(os.getenv("OPENROUTER_API_KEY") or "").strip(),
            str(os.getenv("OPENROUTER_BASE_URL") or "").strip()
            or "https://openrouter.ai/api/v1",
        ),
    )
    configured_candidates = [item for item in candidates if item[0]]
    for configured_key, trusted_base_url in configured_candidates:
        if trusted_base_url and base_urls_match(base_url, trusted_base_url):
            return configured_key

    if configured_candidates:
        raise ValueError(
            "Server-managed OpenAI-compatible API keys may only be used with "
            "their configured provider base URL. Supply an explicit api_key "
            "for a custom endpoint."
        )
    return "sk-no-key-required"


def build_llm(
    *,
    model: str,
    base_url: str,
    api_key: str | None = None,
    temperature: float = 0.3,
):
    """构建 OpenAI-compatible ChatModel；仅在实际选中该 provider 时导入依赖。"""
    from langchain_openai import ChatOpenAI

    # 给云端兼容接口更宽松的网络超时，避免底层 HTTP 先于上层预算截断。
    request_timeout = float(os.getenv("CLOUD_LLM_TIMEOUT_SECONDS", "120"))
    resolved_api_key = _resolve_api_key(base_url=base_url, api_key=api_key)

    logger.info("使用 OpenAI-compatible 模型: %s (地址: %s)", model, base_url)
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        timeout=request_timeout,
        max_retries=0,
        api_key=SecretStr(resolved_api_key),
        base_url=base_url,
    )
