"""DeepSeek OpenAI-compatible LLM provider implementation."""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def build_llm(
    *,
    model: str,
    base_url: str,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
):
    """Build a DeepSeek ChatModel; heavy LangChain imports stay provider-lazy."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "DeepSeek provider requires optional dependency 'langchain-openai'. "
            "Install it before selecting provider='deepseek'."
        ) from exc

    resolved_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not resolved_api_key:
        raise ValueError(
            "DeepSeek provider requires an API key. Set DEEPSEEK_API_KEY or pass api_key."
        )

    request_timeout = float(os.getenv("CLOUD_LLM_TIMEOUT_SECONDS", "120"))
    logger.info("使用 DeepSeek 模型: %s (地址: %s)", model, base_url)
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        timeout=request_timeout,
        max_retries=0,
        api_key=resolved_api_key,
        base_url=base_url,
    )
