"""Ollama LLM provider implementation."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from backend.core.outbound_http import (
    OutboundRequestError,
    OutboundURLBlockedError,
    append_url_path,
    base_urls_match,
    request_public_url,
    request_trusted_url,
)

logger = logging.getLogger(__name__)
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODELS_MAX_RESPONSE_BYTES = 1024 * 1024


def build_llm(
    *,
    model: str,
    base_url: str,
    api_key: str | None = None,
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
    base_url: str | None = None,
    *,
    timeout: float = 5.0,
    route_logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """List installed Ollama model names for routes and compatibility wrappers."""

    log = route_logger or logger
    try:
        configured_base_url = str(
            os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
        ).strip()
        requested_base_url = str(base_url or configured_base_url).strip()
        request_url = append_url_path(requested_base_url, "/api/tags")
        try:
            response = await request_public_url(
                request_url,
                timeout_seconds=timeout,
                max_response_bytes=OLLAMA_MODELS_MAX_RESPONSE_BYTES,
            )
        except OutboundURLBlockedError:
            if not base_urls_match(requested_base_url, configured_base_url):
                raise
            response = await request_trusted_url(
                request_url,
                timeout_seconds=timeout,
                max_response_bytes=OLLAMA_MODELS_MAX_RESPONSE_BYTES,
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("models", []), list):
            raise ValueError("Ollama returned an invalid models payload.")
        models = payload.get("models", [])
        model_names: list[str] = []
        for model in models:
            if not isinstance(model, dict):
                continue
            name = str(model.get("name") or "").strip()
            if name:
                model_names.append(name)
        return {"models": model_names}
    except (OutboundRequestError, httpx.HTTPError, ValueError) as exc:
        log.warning("Cannot reach Ollama: %s", exc)
        return {"models": [], "error": str(exc)}
