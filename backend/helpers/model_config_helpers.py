from __future__ import annotations

from typing import Any, Callable, TypeVar


TModelConfig = TypeVar("TModelConfig")


def model_config_payload(model_config: Any) -> dict[str, Any]:
    if isinstance(model_config, dict):
        return dict(model_config)
    if hasattr(model_config, "model_dump"):
        return model_config.model_dump()
    return model_config.dict()


def base_model_payload(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
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
    data["base_url"] = str(
        data.get("base_url") or default_base_url_for_connection_type(connection_type)
    ).strip()
    data["model"] = str(
        data.get("model") or default_model_for_connection_type(connection_type)
    ).strip()
    data["api_key"] = str(data.get("api_key") or "").strip()
    data["api_key_ref"] = str(data.get("api_key_ref") or "").strip()
    return model_config_cls(**data)
