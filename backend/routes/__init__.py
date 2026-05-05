"""Backend route modules."""

from backend.routes.access_routes import build_access_router
from backend.routes.chat_routes import build_chat_router
from backend.routes.content_routes import build_content_router
from backend.routes.identity_routes import build_identity_router
from backend.routes.kb_routes import (
    TestRetrievalRequest,
    UpdateKBChunkRequest,
    build_kb_router,
)
from backend.routes.operations_routes import (
    SaveConfigRequest,
    TestIntegratorConnectorRequest,
    UpsertIntegratorConnectorsRequest,
    UpsertIntegratorSchedulesRequest,
    UpsertCloudModelApiKeyRequest,
    build_operations_router,
)
from backend.routes.prompt_routes import (
    CreatePromptRequest,
    UpdatePromptRequest,
    build_prompt_router,
)
from backend.routes.security_routes import SaveSsoConfigRequest, build_security_router
from backend.routes.session_routes import build_session_router

__all__ = [
    "CreatePromptRequest",
    "SaveConfigRequest",
    "SaveSsoConfigRequest",
    "TestRetrievalRequest",
    "TestIntegratorConnectorRequest",
    "UpdatePromptRequest",
    "UpdateKBChunkRequest",
    "UpsertCloudModelApiKeyRequest",
    "UpsertIntegratorConnectorsRequest",
    "UpsertIntegratorSchedulesRequest",
    "build_access_router",
    "build_chat_router",
    "build_content_router",
    "build_identity_router",
    "build_kb_router",
    "build_operations_router",
    "build_prompt_router",
    "build_security_router",
    "build_session_router",
]
