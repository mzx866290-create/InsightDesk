"""Application config adapters for API route wiring."""

from __future__ import annotations

from typing import Any, Callable

from backend.core.config_runtime import (
    delete_cloud_model_api_key as delete_cloud_model_api_key_impl,
    sync_runtime_secret_from_store as sync_runtime_secret_from_store_impl,
    upsert_cloud_model_api_key as upsert_cloud_model_api_key_impl,
    validate_tavily_api_key as validate_tavily_api_key_impl,
)


def sync_runtime_secret_from_store(
    store_getter: Callable[[], Any],
    logger: Any,
    env_name: str,
    config_key: str,
) -> str:
    return sync_runtime_secret_from_store_impl(
        store_getter(),
        logger,
        env_name,
        config_key,
    )


def upsert_cloud_model_api_key(
    store_getter: Callable[[], Any],
    api_key_ref: str | None,
    api_key: str,
) -> str:
    return upsert_cloud_model_api_key_impl(store_getter(), api_key_ref, api_key)


def delete_cloud_model_api_key(
    store_getter: Callable[[], Any],
    api_key_ref: str,
) -> bool:
    return delete_cloud_model_api_key_impl(store_getter(), api_key_ref)


async def validate_tavily_api_key(api_key: str) -> None:
    await validate_tavily_api_key_impl(api_key)
