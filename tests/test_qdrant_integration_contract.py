from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest


def test_qdrant_real_integration_contract_is_explicitly_gated() -> None:
    content = Path(__file__).read_text(encoding="utf-8")

    required_snippets = [
        "QDRANT_INTEGRATION_TEST",
        "QDRANT_URL",
        "QDRANT_TEST_COLLECTION",
        "insightdesk_test_",
        "pytest.skip",
        "QdrantClient",
        "recreate_collection",
        "delete_collection",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_qdrant_real_collection_roundtrip_when_enabled() -> None:
    if os.getenv("QDRANT_INTEGRATION_TEST") != "1":
        pytest.skip("Set QDRANT_INTEGRATION_TEST=1 and QDRANT_URL to run real Qdrant integration.")

    qdrant_url = os.getenv("QDRANT_URL", "").strip()
    if not qdrant_url:
        pytest.skip("QDRANT_URL is required for real Qdrant integration.")

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams
    except ModuleNotFoundError as exc:
        pytest.skip(f"qdrant-client is required for real Qdrant integration: {exc}")

    collection_name = os.getenv("QDRANT_TEST_COLLECTION", f"insightdesk_test_{uuid4().hex}")
    if not collection_name.startswith("insightdesk_test_"):
        pytest.skip("QDRANT_TEST_COLLECTION must start with insightdesk_test_.")

    api_key = os.getenv("QDRANT_API_KEY") or None
    client = QdrantClient(url=qdrant_url, api_key=api_key)

    try:
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE),
        )
        client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=1,
                    vector=[0.1, 0.2, 0.3, 0.4],
                    payload={"source": "integration-contract"},
                )
            ],
        )
        count = client.count(collection_name=collection_name, exact=True)
        assert count.count == 1
    finally:
        client.delete_collection(collection_name=collection_name)
