"""Compatibility re-export for ``backend.routes.prompt_routes``."""

from backend.routes.prompt_routes import (
    CreatePromptRequest,
    UpdatePromptRequest,
    build_prompt_router,
)

__all__ = ["CreatePromptRequest", "UpdatePromptRequest", "build_prompt_router"]
