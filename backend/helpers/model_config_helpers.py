from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from backend.core.outbound_http import base_urls_match

TModelConfig = TypeVar("TModelConfig")


def model_config_payload(model_config: Any) -> dict[str, Any]:
    if isinstance(model_config, dict):
        return dict(model_config)
    if hasattr(model_config, "model_dump"):
        payload: dict[str, Any] = model_config.model_dump()
        return payload
    payload = model_config.dict()
    return dict(payload)


def base_model_payload(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        payload: dict[str, Any] = model.model_dump()
        return payload
    if hasattr(model, "dict"):
        payload = model.dict()
        return dict(payload)
    return dict(model)


def normalize_model_config(
    model_config: Any,
    *,
    model_config_cls: Callable[..., TModelConfig],
    normalize_connection_type: Callable[[Any, Any], str],
    default_base_url_for_connection_type: Callable[[str], str],
    default_model_for_connection_type: Callable[[str], str],
) -> TModelConfig:
    data = model_config_payload(model_config)
    connection_type = normalize_connection_type(
        data.get("connection_type") or data.get("provider"),
        data.get("base_url"),
    )
    data["connection_type"] = connection_type
    data["provider"] = connection_type
    requested_base_url = str(data.get("base_url") or "").strip()
    trusted_base_url = str(default_base_url_for_connection_type(connection_type) or "").strip()
    data["base_url"] = requested_base_url or trusted_base_url
    data["model"] = str(
        data.get("model") or default_model_for_connection_type(connection_type)
    ).strip()
    data["api_key"] = str(data.get("api_key") or "").strip()
    data["api_key_ref"] = str(data.get("api_key_ref") or "").strip()

    # Custom endpoints require either a key supplied in the same request or a
    # persisted key ref. Ref-to-endpoint binding is enforced when the secret is
    # resolved, before it can reach the provider client.
    if (
        connection_type == "openai_compatible"
        and requested_base_url
        and not data["api_key"]
        and not data["api_key_ref"]
        and not base_urls_match(requested_base_url, trusted_base_url)
    ):
        raise ValueError(
            "Custom OpenAI-compatible base_url requires an explicit api_key "
            "or a bound api_key_ref."
        )
    return model_config_cls(**data)
