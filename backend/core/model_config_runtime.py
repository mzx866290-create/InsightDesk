"""Model configuration adapters shared by API routes and runtime helpers."""

from __future__ import annotations

from typing import Any

from backend.helpers.model_config_helpers import (
    base_model_payload as base_model_payload_impl,
    model_config_payload as model_config_payload_impl,
    normalize_model_config as normalize_model_config_impl,
)
from backend.core.config_runtime import (
    resolve_model_api_key as resolve_config_model_api_key,
)
from backend.schemas.api_models import ModelConfig


def model_config_payload(mc: ModelConfig | dict[str, Any]) -> dict[str, Any]:
    return model_config_payload_impl(mc)


def base_model_payload(model: Any) -> dict[str, Any]:
    return base_model_payload_impl(model)


def normalize_model_config(mc: ModelConfig | dict[str, Any]) -> ModelConfig:
    from backend.agent.connection import (
        default_base_url_for_connection_type,
        default_model_for_connection_type,
        normalize_connection_type,
    )

    return normalize_model_config_impl(
        mc,
        model_config_cls=ModelConfig,
        normalize_connection_type=normalize_connection_type,
        default_base_url_for_connection_type=default_base_url_for_connection_type,
        default_model_for_connection_type=default_model_for_connection_type,
    )


def resolve_model_api_key(store: Any, logger: Any, mc: ModelConfig | dict[str, Any]) -> str:
    return resolve_config_model_api_key(
        store,
        logger,
        mc,
        model_config_payload=model_config_payload,
    )


def resolve_runtime_model_config(
    store: Any, logger: Any, mc: ModelConfig | dict[str, Any]
) -> ModelConfig:
    normalized = normalize_model_config(mc)
    return ModelConfig(
        **{
            **model_config_payload(normalized),
            "api_key": resolve_model_api_key(store, logger, normalized),
        }
    )
