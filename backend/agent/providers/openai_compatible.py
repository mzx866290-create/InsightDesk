"""OpenAI-compatible LLM provider implementation."""

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
    """构建 OpenAI-compatible ChatModel；仅在实际选中该 provider 时导入依赖。"""
    from langchain_openai import ChatOpenAI

    # 给云端兼容接口更宽松的网络超时，避免底层 HTTP 先于上层预算截断。
    request_timeout = float(os.getenv("CLOUD_LLM_TIMEOUT_SECONDS", "120"))
    resolved_api_key = (
        api_key
        or os.getenv("OPENAI_COMPAT_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or "sk-no-key-required"
    )

    logger.info("使用 OpenAI-compatible 模型: %s (地址: %s)", model, base_url)
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        timeout=request_timeout,
        max_retries=0,
        api_key=resolved_api_key,
        base_url=base_url,
    )
