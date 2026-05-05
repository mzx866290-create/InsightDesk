"""Compatibility re-export for ``backend.routes.kb_routes``."""

from backend.routes.kb_routes import (
    TestRetrievalRequest,
    UpdateKBChunkRequest,
    build_kb_router,
)

__all__ = [
    "TestRetrievalRequest",
    "UpdateKBChunkRequest",
    "build_kb_router",
]
