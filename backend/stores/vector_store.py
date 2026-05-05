"""Vector store provider boundary for knowledge-base retrieval."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from langchain_core.documents import Document

from backend.core.storage_runtime import (
    VECTOR_STORE_PROVIDER_FAISS,
    VECTOR_STORE_PROVIDER_QDRANT,
    assert_supported_vector_store_provider,
    qdrant_api_key,
    qdrant_collection_name,
    qdrant_url,
    vector_store_runtime_summary,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStoreAdapter(Protocol):
    provider: str

    def from_documents(self, documents: list[Document], embeddings: Any) -> Any: ...

    def load(self, *, embeddings: Any, path: str | None = None) -> Any: ...

    def save(self, vectorstore: Any, *, path: str | None = None) -> None: ...

    def delete(self, *, path: str | None = None) -> bool: ...

    def clear(self, *, path: str | None = None) -> bool: ...

    def validation_summary(self, *, path: str | None = None) -> dict[str, Any]: ...


@dataclass(frozen=True)
class FaissVectorStoreAdapter:
    path: str
    provider: str = VECTOR_STORE_PROVIDER_FAISS

    def from_documents(self, documents: list[Document], embeddings: Any) -> Any:
        from langchain_community.vectorstores import FAISS

        return FAISS.from_documents(documents, embeddings)

    def load(self, *, embeddings: Any, path: str | None = None) -> Any:
        from langchain_community.vectorstores import FAISS

        return FAISS.load_local(
            path or self.path,
            embeddings,
            allow_dangerous_deserialization=True,
        )

    def save(self, vectorstore: Any, *, path: str | None = None) -> None:
        vectorstore.save_local(path or self.path)

    def delete(self, *, path: str | None = None) -> bool:
        target_dir = Path(path or self.path)
        if not target_dir.exists():
            return False
        try:
            shutil.rmtree(target_dir)
            return True
        except Exception:
            logger.exception("FAISS vector store delete failed: %s", target_dir)
            return False

    def clear(self, *, path: str | None = None) -> bool:
        return self.delete(path=path)

    def validation_summary(self, *, path: str | None = None) -> dict[str, Any]:
        return vector_store_runtime_summary(
            provider=self.provider,
            path=path or self.path,
            delete_supported=True,
            clear_supported=True,
        )


@dataclass(frozen=True)
class QdrantVectorStoreAdapter:
    collection_name: str
    url: str = "http://localhost:6333"
    api_key: str = ""
    provider: str = VECTOR_STORE_PROVIDER_QDRANT
    client_factory: Callable[..., Any] | None = None

    def _vector_store_class(self):
        try:
            from langchain_qdrant import QdrantVectorStore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "VECTOR_STORE_PROVIDER=qdrant requires langchain-qdrant and qdrant-client."
            ) from exc
        return QdrantVectorStore

    def _client(self) -> Any:
        if self.client_factory is not None:
            return self.client_factory(
                url=self.url,
                api_key=self.api_key or None,
            )

        try:
            from qdrant_client import QdrantClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "VECTOR_STORE_PROVIDER=qdrant requires langchain-qdrant and qdrant-client."
            ) from exc
        return QdrantClient(url=self.url, api_key=self.api_key or None)

    @staticmethod
    def _operation_succeeded(result: Any) -> bool:
        if isinstance(result, bool):
            return result
        if result is None:
            return True

        status = getattr(result, "status", None)
        if status is None and isinstance(result, dict):
            status = result.get("status")
        if status is None:
            return bool(result)

        normalized = str(getattr(status, "value", status)).strip().lower()
        return normalized in {"acknowledged", "completed", "ok", "success", "true"}

    @staticmethod
    def _all_points_selector() -> Any:
        try:
            from qdrant_client import models
        except ModuleNotFoundError:
            return {"filter": {"must": []}}
        return models.FilterSelector(filter=models.Filter(must=[]))

    def from_documents(self, documents: list[Document], embeddings: Any) -> Any:
        vector_store_class = self._vector_store_class()
        return vector_store_class.from_documents(
            documents,
            embedding=embeddings,
            url=self.url,
            api_key=self.api_key or None,
            collection_name=self.collection_name,
        )

    def load(self, *, embeddings: Any, path: str | None = None) -> Any:
        del path
        vector_store_class = self._vector_store_class()
        return vector_store_class.from_existing_collection(
            embedding=embeddings,
            url=self.url,
            api_key=self.api_key or None,
            collection_name=self.collection_name,
        )

    def save(self, vectorstore: Any, *, path: str | None = None) -> None:
        del vectorstore, path
        # Qdrant persists on write; no local save operation is required.
        return None

    def delete(self, *, path: str | None = None) -> bool:
        del path
        try:
            result = self._client().delete_collection(
                collection_name=self.collection_name,
            )
            return self._operation_succeeded(result)
        except Exception:
            logger.exception(
                "Qdrant collection delete failed: %s",
                self.collection_name,
            )
            return False

    def clear(self, *, path: str | None = None) -> bool:
        del path
        try:
            result = self._client().delete(
                collection_name=self.collection_name,
                points_selector=self._all_points_selector(),
            )
            return self._operation_succeeded(result)
        except Exception:
            logger.exception(
                "Qdrant collection clear failed: %s",
                self.collection_name,
            )
            return False

    def validation_summary(self, *, path: str | None = None) -> dict[str, Any]:
        del path
        return vector_store_runtime_summary(
            provider=self.provider,
            collection_name=self.collection_name,
            url=self.url,
            api_key=self.api_key,
            delete_supported=True,
            clear_supported=True,
        )


def create_vector_store_adapter(
    *,
    provider: str | None = None,
    path: str = "./vector_store",
    collection_name: str | None = None,
) -> VectorStoreAdapter:
    normalized_provider = provider or assert_supported_vector_store_provider()
    if normalized_provider == VECTOR_STORE_PROVIDER_FAISS:
        return FaissVectorStoreAdapter(path=path)
    if normalized_provider == VECTOR_STORE_PROVIDER_QDRANT:
        return QdrantVectorStoreAdapter(
            collection_name=collection_name or qdrant_collection_name(),
            url=qdrant_url(),
            api_key=qdrant_api_key(),
        )
    raise RuntimeError(f"Unsupported vector store provider: {normalized_provider}")
