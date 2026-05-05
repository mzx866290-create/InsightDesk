"""Env-gated FAISS-to-Qdrant embedding backfill runner.

Default mode is a side-effect-free plan: it validates local paths and target
configuration, but it does not deserialize FAISS, connect to Qdrant, or write
points. Real backfill requires --execute and QDRANT_BACKFILL_EXECUTE=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.storage_runtime import (  # noqa: E402
    validate_qdrant_config,
)


QDRANT_BACKFILL_EXECUTE_ENV = "QDRANT_BACKFILL_EXECUTE"
DEFAULT_BATCH_SIZE = 64
DEFAULT_VECTOR_SIZE = 1536


@dataclass(frozen=True)
class BackfillDocument:
    page_content: str
    metadata: dict[str, Any]


EmbedderFactory = Callable[[str, str], Any]
QdrantClientFactory = Callable[..., Any]


def _path_snapshot(path: str) -> dict[str, Any]:
    normalized = str(path or "").strip()
    target = Path(normalized or "./vector_store").expanduser()
    return {
        "path": normalized,
        "absolute_path": str(target.resolve(strict=False)),
        "exists": target.exists(),
        "is_dir": target.is_dir(),
        "index_faiss_exists": (target / "index.faiss").is_file(),
        "index_pkl_exists": (target / "index.pkl").is_file(),
    }


def _document_id(collection_name: str, document: BackfillDocument, ordinal: int) -> str:
    metadata = document.metadata or {}
    source = str(metadata.get("source") or metadata.get("file_path") or "").strip()
    content_hash = hashlib.sha1(
        document.page_content.encode("utf-8", "ignore")
    ).hexdigest()
    seed = f"{collection_name}:{source}:{content_hash}:{ordinal}"
    return str(uuid5(NAMESPACE_URL, seed))


def _iter_batches(items: list[BackfillDocument], batch_size: int) -> Iterable[list[BackfillDocument]]:
    normalized_batch_size = max(1, int(batch_size or DEFAULT_BATCH_SIZE))
    for start in range(0, len(items), normalized_batch_size):
        yield items[start : start + normalized_batch_size]


def load_faiss_documents(
    vector_store_path: str,
    *,
    embedding_model: str,
    device: str,
    allow_dangerous_deserialization: bool,
    embedder_factory: EmbedderFactory | None = None,
) -> list[BackfillDocument]:
    """Load historical FAISS documents after explicit pickle opt-in."""

    if not allow_dangerous_deserialization:
        raise RuntimeError("allow_dangerous_faiss_deserialization_required")

    try:
        from langchain_community.vectorstores import FAISS
    except ModuleNotFoundError as exc:
        raise RuntimeError("langchain-community is required to load FAISS history.") from exc

    embeddings = (
        embedder_factory(embedding_model, device)
        if embedder_factory is not None
        else _create_embeddings(embedding_model, device)
    )
    vectorstore = FAISS.load_local(
        vector_store_path,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    docstore_items = getattr(getattr(vectorstore, "docstore", None), "_dict", {})
    index_to_docstore_id = getattr(vectorstore, "index_to_docstore_id", {})
    ordered_ids = [
        docstore_id
        for _, docstore_id in sorted(index_to_docstore_id.items(), key=lambda item: item[0])
    ]
    if not ordered_ids:
        ordered_ids = list(docstore_items.keys())

    documents: list[BackfillDocument] = []
    seen: set[str] = set()
    for docstore_id in ordered_ids:
        if docstore_id in seen:
            continue
        seen.add(str(docstore_id))
        raw_doc = docstore_items.get(docstore_id)
        page_content = str(getattr(raw_doc, "page_content", "") or "")
        if not page_content.strip():
            continue
        metadata = dict(getattr(raw_doc, "metadata", {}) or {})
        metadata.setdefault("legacy_faiss_docstore_id", str(docstore_id))
        documents.append(BackfillDocument(page_content=page_content, metadata=metadata))
    return documents


def _create_embeddings(embedding_model: str, device: str) -> Any:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ModuleNotFoundError as exc:
        raise RuntimeError("langchain-huggingface is required for Qdrant backfill.") from exc

    return HuggingFaceEmbeddings(
        model_name=embedding_model,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )


def _ensure_collection(client: Any, collection_name: str, vector_size: int) -> bool:
    try:
        from qdrant_client.models import Distance, VectorParams
    except ModuleNotFoundError as exc:
        raise RuntimeError("qdrant-client is required for Qdrant backfill.") from exc

    collections = client.get_collections()
    names = {
        str(item.name)
        for item in getattr(collections, "collections", [])
        if getattr(item, "name", None)
    }
    if collection_name in names:
        return False

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=max(1, int(vector_size)), distance=Distance.COSINE),
    )
    return True


def execute_qdrant_backfill(
    *,
    documents: list[BackfillDocument],
    qdrant_url: str,
    qdrant_api_key: str,
    collection_name: str,
    embedding_model: str,
    device: str,
    vector_size: int,
    batch_size: int,
    embedder_factory: EmbedderFactory | None = None,
    qdrant_client_factory: QdrantClientFactory | None = None,
) -> dict[str, Any]:
    """Embed historical documents and upsert deterministic points into Qdrant."""

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
    except ModuleNotFoundError as exc:
        raise RuntimeError("qdrant-client is required for Qdrant backfill.") from exc

    embeddings = (
        embedder_factory(embedding_model, device)
        if embedder_factory is not None
        else _create_embeddings(embedding_model, device)
    )
    client = (
        qdrant_client_factory(url=qdrant_url, api_key=qdrant_api_key or None)
        if qdrant_client_factory is not None
        else QdrantClient(url=qdrant_url, api_key=qdrant_api_key or None)
    )
    created = _ensure_collection(client, collection_name, vector_size)

    upserted = 0
    for batch_index, batch in enumerate(_iter_batches(documents, batch_size)):
        texts = [document.page_content for document in batch]
        vectors = embeddings.embed_documents(texts)
        points = [
            PointStruct(
                id=_document_id(collection_name, document, upserted + offset),
                vector=vector,
                payload={
                    "page_content": document.page_content,
                    "metadata": {
                        **document.metadata,
                        "qdrant_backfill_source": "faiss",
                        "qdrant_backfill_batch": batch_index,
                    },
                },
            )
            for offset, (document, vector) in enumerate(zip(batch, vectors))
        ]
        if points:
            client.upsert(collection_name=collection_name, points=points)
            upserted += len(points)

    return {
        "checked": True,
        "collection": collection_name,
        "created_collection": created,
        "documents_loaded": len(documents),
        "upserted": upserted,
        "remaining": max(0, len(documents) - upserted),
        "errors": [],
        "warnings": [],
    }


def build_backfill_report(
    args: argparse.Namespace,
    *,
    document_loader: Callable[..., list[BackfillDocument]] = load_faiss_documents,
    executor: Callable[..., dict[str, Any]] = execute_qdrant_backfill,
) -> dict[str, Any]:
    vector_store_path = str(args.vector_store_path or os.getenv("VECTOR_STORE_PATH") or "./vector_store").strip()
    qdrant_url = str(args.qdrant_url or os.getenv("QDRANT_URL") or "").strip()
    qdrant_collection = str(args.qdrant_collection or os.getenv("QDRANT_COLLECTION") or "insightdesk_kb").strip()
    qdrant_api_key = str(args.qdrant_api_key or os.getenv("QDRANT_API_KEY") or "").strip()
    embedding_model = str(args.embedding_model or os.getenv("EMBEDDING_MODEL") or "BAAI/bge-base-zh-v1.5").strip()
    device = str(args.device or os.getenv("EMBEDDING_DEVICE") or "cpu").strip()

    source = _path_snapshot(vector_store_path)
    target = validate_qdrant_config(
        url=qdrant_url,
        collection_name=qdrant_collection,
        api_key=qdrant_api_key,
    )
    warnings = list(target.get("warnings", []))
    errors: list[str] = []
    actions: dict[str, Any] = {
        "mode": "execute" if args.execute else "plan",
        "executed": False,
        "dry_run": not args.execute,
        "env_gate": QDRANT_BACKFILL_EXECUTE_ENV,
        "command": [
            "python",
            "deploy/run_qdrant_backfill.py",
            "--execute",
            "--allow-dangerous-faiss-deserialization",
            "--json",
        ],
    }

    if not source["exists"] or not source["is_dir"]:
        errors.append("faiss_source_path_missing")
    if not source["index_faiss_exists"]:
        errors.append("faiss_index_file_missing")
    if not source["index_pkl_exists"]:
        errors.append("faiss_docstore_file_missing")
    if not target["valid"]:
        errors.append("qdrant_target_invalid")
    if args.execute and os.getenv(QDRANT_BACKFILL_EXECUTE_ENV) != "1":
        errors.append(f"missing_env:{QDRANT_BACKFILL_EXECUTE_ENV}")
    if args.execute and not args.allow_dangerous_faiss_deserialization:
        errors.append("allow_dangerous_faiss_deserialization_required")

    documents_loaded: int | None = None
    execution: dict[str, Any] = {"checked": False, "skipped": True}
    if args.execute and not errors:
        documents = document_loader(
            vector_store_path,
            embedding_model=embedding_model,
            device=device,
            allow_dangerous_deserialization=args.allow_dangerous_faiss_deserialization,
        )
        documents_loaded = len(documents)
        execution = executor(
            documents=documents,
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            collection_name=qdrant_collection,
            embedding_model=embedding_model,
            device=device,
            vector_size=int(args.qdrant_vector_size),
            batch_size=int(args.batch_size),
        )
        actions["executed"] = True
        execution["skipped"] = False
        warnings.extend(execution.get("warnings", []))
        errors.extend(execution.get("errors", []))

    if args.execute:
        remaining = execution.get("remaining") if execution.get("checked") else None
    else:
        remaining = None

    return {
        "ok": not errors,
        "source": {"faiss": source},
        "target": {"qdrant": target},
        "plan": {
            "source_documents": documents_loaded,
            "target_collection": qdrant_collection,
            "batch_size": int(args.batch_size),
            "vector_size": int(args.qdrant_vector_size),
            "remaining": remaining,
            "side_effect_free": not args.execute,
        },
        "embedding": {"model": embedding_model, "device": device},
        "actions": actions,
        "execution": execution,
        "warnings": warnings,
        "errors": errors,
    }


def _print_text_report(report: dict[str, Any]) -> None:
    print("Qdrant backfill plan")
    print(f"- Source: {report['source']['faiss']['absolute_path']}")
    print(f"- Target collection: {report['plan']['target_collection']}")
    print(f"- Mode: {report['actions']['mode']}")
    print(f"- Dry run: {report['actions']['dry_run']}")
    print(f"- Remaining: {report['plan']['remaining']}")
    if report["warnings"]:
        print("- Warnings: " + ", ".join(report["warnings"]))
    if report["errors"]:
        print("- Errors: " + ", ".join(report["errors"]))
    print(f"- OK: {report['ok']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or execute an env-gated FAISS-to-Qdrant embedding backfill."
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--execute", action="store_true", help="Run the real Qdrant backfill.")
    parser.add_argument("--vector-store-path", default="")
    parser.add_argument("--qdrant-url", default="")
    parser.add_argument("--qdrant-collection", default="")
    parser.add_argument("--qdrant-api-key", default="")
    parser.add_argument("--qdrant-vector-size", type=int, default=DEFAULT_VECTOR_SIZE)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--device", default="")
    parser.add_argument(
        "--allow-dangerous-faiss-deserialization",
        action="store_true",
        help="Required for --execute because FAISS docstore loading uses pickle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_backfill_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text_report(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
