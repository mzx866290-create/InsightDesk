"""Connection aliases and LLM factory for the split agent runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable, Optional


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
DEEPSEEK_CONNECTION_ALIASES = {
    "deepseek",
    "deepseek_compatible",
}
ANTHROPIC_CONNECTION_ALIASES = {
    "anthropic",
    "claude",
}
GOOGLE_CONNECTION_ALIASES = {
    "google",
    "gemini",
}

LLMProviderFactory = Callable[..., Any]


@dataclass(frozen=True)
class LLMProviderRegistration:
    """轻量 LLM Provider 注册项，仅保存惰性导入所需的元数据。"""

    connection_type: str
    aliases: frozenset[str]
    factory_module: str
    factory_name: str
    base_url_env_keys: tuple[str, ...]
    default_base_url: str
    model_env_keys: tuple[str, ...]
    default_model: str
    capabilities: tuple[str, ...] = ("chat",)

    def load_factory(self) -> LLMProviderFactory:
        module = import_module(self.factory_module)
        return getattr(module, self.factory_name)


LLM_PROVIDER_REGISTRY: dict[str, LLMProviderRegistration] = {
    "ollama": LLMProviderRegistration(
        connection_type="ollama",
        aliases=frozenset(OLLAMA_CONNECTION_ALIASES),
        factory_module="backend.agent.providers.ollama",
        factory_name="build_llm",
        base_url_env_keys=("OLLAMA_BASE_URL",),
        default_base_url="http://localhost:11434",
        model_env_keys=("OLLAMA_MODEL",),
        default_model="qwen3.5-2B:latest",
    ),
    "openai_compatible": LLMProviderRegistration(
        connection_type="openai_compatible",
        aliases=frozenset(OPENAI_COMPAT_CONNECTION_ALIASES),
        factory_module="backend.agent.providers.openai_compatible",
        factory_name="build_llm",
        base_url_env_keys=(
            "OPENAI_COMPAT_BASE_URL",
            "OPENAI_BASE_URL",
            "OPENROUTER_BASE_URL",
        ),
        default_base_url="https://openrouter.ai/api/v1",
        model_env_keys=(
            "OPENAI_COMPAT_MODEL",
            "OPENAI_MODEL",
            "OPENROUTER_MODEL",
        ),
        default_model="gpt-4o-mini",
    ),
    "deepseek": LLMProviderRegistration(
        connection_type="deepseek",
        aliases=frozenset(DEEPSEEK_CONNECTION_ALIASES),
        factory_module="backend.agent.providers.deepseek",
        factory_name="build_llm",
        base_url_env_keys=("DEEPSEEK_BASE_URL", "OPENAI_COMPAT_BASE_URL"),
        default_base_url="https://api.deepseek.com",
        model_env_keys=("DEEPSEEK_MODEL",),
        default_model="deepseek-chat",
    ),
    "anthropic": LLMProviderRegistration(
        connection_type="anthropic",
        aliases=frozenset(ANTHROPIC_CONNECTION_ALIASES),
        factory_module="backend.agent.providers.anthropic",
        factory_name="build_llm",
        base_url_env_keys=("ANTHROPIC_BASE_URL",),
        default_base_url="",
        model_env_keys=("ANTHROPIC_MODEL",),
        default_model="claude-3-5-sonnet-latest",
    ),
    "google": LLMProviderRegistration(
        connection_type="google",
        aliases=frozenset(GOOGLE_CONNECTION_ALIASES),
        factory_module="backend.agent.providers.google",
        factory_name="build_llm",
        base_url_env_keys=("GOOGLE_BASE_URL",),
        default_base_url="",
        model_env_keys=("GOOGLE_MODEL", "GEMINI_MODEL"),
        default_model="gemini-2.0-flash",
    ),
}

_CONNECTION_TYPE_BY_ALIAS: dict[str, str] = {
    alias: registration.connection_type
    for registration in LLM_PROVIDER_REGISTRY.values()
    for alias in registration.aliases
}


def _first_env_value(env_keys: tuple[str, ...]) -> str:
    for env_key in env_keys:
        value = os.getenv(env_key)
        if value:
            return value
    return ""


def _get_provider_registration(connection_type: str) -> LLMProviderRegistration:
    try:
        return LLM_PROVIDER_REGISTRY[connection_type]
    except KeyError as exc:
        raise ValueError(f"不支持的连接类型: {connection_type}") from exc


def normalize_connection_type(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """Normalize legacy provider names into a compatibility-first connection type."""
    raw_provider = (provider or "").strip().lower()
    raw_base_url = (base_url or "").strip().lower()

    if raw_provider in _CONNECTION_TYPE_BY_ALIAS:
        return _CONNECTION_TYPE_BY_ALIAS[raw_provider]

    if raw_base_url:
        if "deepseek" in raw_base_url:
            return "deepseek"
        if "11434" in raw_base_url or raw_base_url.rstrip("/").endswith("ollama"):
            return "ollama"
        return "openai_compatible"

    return "ollama"


def default_base_url_for_connection_type(connection_type: str) -> str:
    registration = _get_provider_registration(normalize_connection_type(connection_type))
    return _first_env_value(registration.base_url_env_keys) or registration.default_base_url


def default_model_for_connection_type(connection_type: str) -> str:
    registration = _get_provider_registration(normalize_connection_type(connection_type))
    return _first_env_value(registration.model_env_keys) or registration.default_model


def serialize_llm_provider_registration(
    registration: LLMProviderRegistration,
) -> dict[str, Any]:
    """Serialize registry metadata without importing provider runtime dependencies."""
    return {
        "id": registration.connection_type,
        "connection_type": registration.connection_type,
        "aliases": sorted(registration.aliases),
        "capabilities": list(registration.capabilities),
        "default_base_url": default_base_url_for_connection_type(
            registration.connection_type
        ),
        "default_model": default_model_for_connection_type(registration.connection_type),
        "base_url_env_keys": list(registration.base_url_env_keys),
        "model_env_keys": list(registration.model_env_keys),
    }


def list_llm_provider_catalog() -> dict[str, Any]:
    """Return the registered LLM provider catalog for frontend model selectors."""
    providers = [
        serialize_llm_provider_registration(registration)
        for registration in LLM_PROVIDER_REGISTRY.values()
    ]
    return {
        "providers": providers,
        "default_provider": normalize_connection_type(),
        "total": len(providers),
    }


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
        provider: 连接类型或别名，如 `ollama` / `openai_compatible`，也兼容 `local` / `cloud`
        model_name: 模型 ID
        base_url: API Base URL
        api_key: API Key，兼容 OpenAI 接口时可为空，空时会自动注入占位 key
        temperature: 温度参数

    Returns:
        LangChain ChatModel 实例
    """
    connection_type = normalize_connection_type(provider, base_url)
    registration = _get_provider_registration(connection_type)
    factory = registration.load_factory()

    return factory(
        model=model_name or default_model_for_connection_type(connection_type),
        base_url=base_url or default_base_url_for_connection_type(connection_type),
        api_key=api_key,
        temperature=temperature,
    )


__all__ = [
    "LLM_PROVIDER_REGISTRY",
    "LLMProviderRegistration",
    "OLLAMA_CONNECTION_ALIASES",
    "OPENAI_COMPAT_CONNECTION_ALIASES",
    "default_base_url_for_connection_type",
    "default_model_for_connection_type",
    "get_llm",
    "list_llm_provider_catalog",
    "normalize_connection_type",
    "serialize_llm_provider_registration",
]
