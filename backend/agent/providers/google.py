"""Google Gemini LLM provider skeleton with lazy optional dependency import."""

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
    """Build a Google Gemini ChatModel only after this provider is selected."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ImportError(
            "Google provider requires optional dependency 'langchain-google-genai'. "
            "Install it before selecting provider='google'."
        ) from exc

    resolved_api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise ValueError(
            "Google provider requires an API key. Set GOOGLE_API_KEY/GEMINI_API_KEY or pass api_key."
        )

    logger.info("使用 Google Gemini 模型: %s", model)
    kwargs = {
        "model": model,
        "temperature": temperature,
        "google_api_key": resolved_api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatGoogleGenerativeAI(**kwargs)
