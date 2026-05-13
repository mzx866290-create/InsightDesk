from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter


def build_provider_router(
    *,
    provider_catalog_response_model: type,
    list_provider_catalog: Callable[[], dict[str, Any]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/providers", response_model=provider_catalog_response_model)
    async def list_providers():
        # Catalog 只序列化已注册 provider 元数据，避免触发 LangChain runtime 导入。
        return list_provider_catalog()

    return router
