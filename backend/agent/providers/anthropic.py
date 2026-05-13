"""Anthropic LLM provider skeleton with lazy optional dependency import."""

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
    """Build an Anthropic ChatModel only after this provider is selected."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise ImportError(
            "Anthropic provider requires optional dependency 'langchain-anthropic'. "
            "Install it before selecting provider='anthropic'."
        ) from exc

    resolved_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not resolved_api_key:
        raise ValueError(
            "Anthropic provider requires an API key. Set ANTHROPIC_API_KEY or pass api_key."
        )

    logger.info("使用 Anthropic 模型: %s", model)
    kwargs = {
        "model": model,
        "temperature": temperature,
        "api_key": resolved_api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatAnthropic(**kwargs)
