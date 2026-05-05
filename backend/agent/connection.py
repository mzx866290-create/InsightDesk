"""Connection aliases and LLM factory for the split agent runtime."""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_CONNECTION_ALIASES = {
    "local",
    "ollama",
    "ollama_local",
}
OPENAI_COMPAT_CONNECTION_ALIASES = {
    "cloud",
    "openai",
    "openai_compatible",
    "openrouter",
    "compatible",
    "api",
}


def normalize_connection_type(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """Normalize legacy provider names into a compatibility-first connection type."""
    raw_provider = (provider or "").strip().lower()
    raw_base_url = (base_url or "").strip().lower()

    if raw_provider in OLLAMA_CONNECTION_ALIASES:
        return "ollama"
    if raw_provider in OPENAI_COMPAT_CONNECTION_ALIASES:
        return "openai_compatible"

    if raw_base_url:
        if "11434" in raw_base_url or raw_base_url.rstrip("/").endswith("ollama"):
            return "ollama"
        return "openai_compatible"

    return "ollama"


def default_base_url_for_connection_type(connection_type: str) -> str:
    normalized = normalize_connection_type(connection_type)
    if normalized == "ollama":
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    return (
        os.getenv("OPENAI_COMPAT_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENROUTER_BASE_URL")
        or "https://openrouter.ai/api/v1"
    )


def default_model_for_connection_type(connection_type: str) -> str:
    normalized = normalize_connection_type(connection_type)
    if normalized == "ollama":
        return os.getenv("OLLAMA_MODEL", "qwen3.5-2B:latest")

    return (
        os.getenv("OPENAI_COMPAT_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or "gpt-4o-mini"
    )


def get_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
):
    """
    模型工厂函数 - 根据兼容连接配置返回对应的 LLM 实例。

    Args:
        provider: 连接类型或其别名（如 `ollama` / `openai_compatible`，也兼容旧的 `local` / `cloud`）
        model_name: 模型 ID
        base_url: API Base URL
        api_key: API Key（兼容 OpenAI 接口时可为空，空时会自动注入占位 key）
        temperature: 温度参数

    Returns:
        LangChain ChatModel 实例
    """
    connection_type = normalize_connection_type(provider, base_url)

    if connection_type == "openai_compatible":
        # OpenAI-compatible 兼容接口。
        from langchain_openai import ChatOpenAI

        base_url = base_url or default_base_url_for_connection_type(connection_type)
        model = model_name or default_model_for_connection_type(connection_type)
        # 默认给云端接口更宽裕的网络超时，避免上层预算未到就先被底层 HTTP 截断。
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

    if connection_type == "ollama":
        # Ollama 本地模型。
        from langchain_ollama import ChatOllama

        model = model_name or default_model_for_connection_type(connection_type)
        base_url = base_url or default_base_url_for_connection_type(connection_type)

        if not re.match(r"^[a-zA-Z0-9._:/-]+$", model):
            raise ValueError(
                f"Invalid Ollama model name: '{model}'. "
                "Model names cannot contain spaces or special characters. "
                "Valid format: name:tag (e.g., qwen3:4b, llama2:7b)"
            )

        logger.info("使用本地模型: %s (地址: %s)", model, base_url)
        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=base_url,
            num_predict=2048,
            top_p=0.9,  # 限制采样范围
        )

    raise ValueError(f"不支持的连接类型: {provider}")


__all__ = [
    "OLLAMA_CONNECTION_ALIASES",
    "OPENAI_COMPAT_CONNECTION_ALIASES",
    "default_base_url_for_connection_type",
    "default_model_for_connection_type",
    "get_llm",
    "normalize_connection_type",
]
