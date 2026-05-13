"""Ollama LLM provider implementation."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


def build_llm(
    *,
    model: str,
    base_url: str,
    api_key: Optional[str] = None,
    temperature: float = 0.3,
):
    """Build an Ollama ChatModel; import LangChain adapter lazily."""

    from langchain_ollama import ChatOllama

    if not re.match(r"^[a-zA-Z0-9._:/-]+$", model):
        raise ValueError(
            f"Invalid Ollama model name: '{model}'. "
            "Model names cannot contain spaces or special characters. "
            "Valid format: name:tag (e.g., qwen3:4b, llama2:7b)"
        )

    logger.info("Using local Ollama model: %s (base_url=%s)", model, base_url)
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        num_predict=2048,
        top_p=0.9,
    )


async def list_ollama_models(
    base_url: str = "http://localhost:11434",
    *,
    timeout: float = 5.0,
    route_logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """List installed Ollama model names for routes and compatibility wrappers."""

    log = route_logger or logger
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url}/api/tags")
        response.raise_for_status()
        models = response.json().get("models", [])
        return {"models": [str(model["name"]) for model in models if "name" in model]}
    except httpx.HTTPError as exc:
        log.warning("Cannot reach Ollama: %s", exc)
        return {"models": [], "error": str(exc)}
