from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langchain_core.documents import Document

from backend.api_kb_chunk_route_helpers import (
    delete_kb_chunk_payload,
    list_kb_chunks_payload,
    update_kb_chunk_payload,
)


def test_list_kb_chunks_payload_returns_empty_page_when_index_missing():
    payload = list_kb_chunks_payload(
        store_path="kb",
        abs_store="/tmp/kb",
        index_exists=False,
        query="",
        source="",
        offset=0,
        limit=20,
        pipeline_factory=lambda path: (_ for _ in ()).throw(AssertionError("should not build pipeline")),
        collect_chunks=lambda pipeline: [],
        filter_chunks=lambda chunks, **kwargs: {},
    )

    assert payload == {
        "items": [],
        "total": 0,
        "offset": 0,
        "limit": 20,
        "has_more": False,
        "store_path": "/tmp/kb",
    }


def test_list_kb_chunks_payload_filters_loaded_chunks():
    events: list[tuple[str, object]] = []
    pipeline = SimpleNamespace(
        vectorstore=object(),
        load_store=lambda: events.append(("load", "kb")) or True,
    )

    payload = list_kb_chunks_payload(
        store_path="kb",
        abs_store="/tmp/kb",
        index_exists=True,
        query="alpha",
        source="brief",
        offset=1,
        limit=2,
        pipeline_factory=lambda path: pipeline,
        collect_chunks=lambda runtime: [
            {"chunk_id": "chunk-1", "content": "alpha", "source": "brief.md"}
        ],
        filter_chunks=lambda chunks, **kwargs: {
            "items": chunks,
            "total": 1,
            "offset": kwargs["offset"],
            "limit": kwargs["limit"],
            "has_more": False,
        },
    )

    assert payload["items"][0]["chunk_id"] == "chunk-1"
    assert payload["store_path"] == "/tmp/kb"
    assert events == [("load", "kb")]


def test_update_kb_chunk_payload_rebuilds_when_content_changes():
    events: list[tuple[str, object]] = []
    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-1": Document(
                    page_content="Old content",
                    metadata={"source": "alpha.md"},
                ),
                "chunk-2": Document(
                    page_content="Keep me",
                    metadata={"source": "beta.md"},
                ),
            }
        )
    )
    pipeline = SimpleNamespace(
        vectorstore=vectorstore,
        load_store=lambda: events.append(("load", None)) or True,
        _save_vectorstore_local=lambda: events.append(("save", None)),
    )

    payload = update_kb_chunk_payload(
        chunk_id="chunk-1",
        request=SimpleNamespace(content="Updated content", source="updated.md"),
        field_set={"content", "source"},
        pipeline_factory=lambda: pipeline,
        docstore_dict=lambda vectorstore: vectorstore.docstore._dict,
        safe_metadata=lambda metadata: dict(metadata),
        rebuild_from_documents=lambda runtime, documents: events.append(
            (
                "rebuild",
                [(doc.page_content, dict(doc.metadata)) for doc in documents],
            )
        ),
        doc_factory=lambda page_content, metadata: Document(
            page_content=page_content,
            metadata=metadata,
        ),
        current_time=lambda: 123.0,
    )

    assert payload == {"ok": True, "chunk_id": "chunk-1", "reindexed": True}
    assert events[0] == ("load", None)
    assert events[1][0] == "rebuild"
    assert events[1][1][0][0] == "Updated content"
    assert events[1][1][0][1]["source"] == "updated.md"
    assert events[1][1][0][1]["kb_last_edited_at"] == 123


def test_update_kb_chunk_payload_saves_when_only_source_changes():
    events: list[tuple[str, object]] = []
    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-1": Document(
                    page_content="Stable content",
                    metadata={"source": "alpha.md"},
                )
            }
        )
    )
    pipeline = SimpleNamespace(
        vectorstore=vectorstore,
        load_store=lambda: True,
        _save_vectorstore_local=lambda: events.append(("save", None)),
    )

    payload = update_kb_chunk_payload(
        chunk_id="chunk-1",
        request=SimpleNamespace(content=None, source="renamed.md"),
        field_set={"source"},
        pipeline_factory=lambda: pipeline,
        docstore_dict=lambda vectorstore: vectorstore.docstore._dict,
        safe_metadata=lambda metadata: dict(metadata),
        rebuild_from_documents=lambda runtime, documents: events.append(("rebuild", documents)),
        doc_factory=lambda page_content, metadata: Document(
            page_content=page_content,
            metadata=metadata,
        ),
        current_time=lambda: 200.0,
    )

    assert payload == {"ok": True, "chunk_id": "chunk-1", "reindexed": False}
    assert events == [("save", None)]


def test_update_kb_chunk_payload_rejects_missing_fields():
    with pytest.raises(HTTPException) as exc_info:
        update_kb_chunk_payload(
            chunk_id="chunk-1",
            request=SimpleNamespace(content=None, source=None),
            field_set=set(),
            pipeline_factory=lambda: object(),
            docstore_dict=lambda vectorstore: {},
            safe_metadata=lambda metadata: {},
            rebuild_from_documents=lambda runtime, documents: None,
            doc_factory=lambda page_content, metadata: None,
        )

    assert exc_info.value.status_code == 400


def test_delete_kb_chunk_payload_rebuilds_remaining_documents():
    events: list[tuple[str, object]] = []
    vectorstore = SimpleNamespace(
        docstore=SimpleNamespace(
            _dict={
                "chunk-1": Document(
                    page_content="Delete me",
                    metadata={"source": "alpha.md"},
                ),
                "chunk-2": Document(
                    page_content="Keep me",
                    metadata={"source": "beta.md"},
                ),
            }
        )
    )
    pipeline = SimpleNamespace(
        vectorstore=vectorstore,
        load_store=lambda: events.append(("load", None)) or True,
    )

    payload = delete_kb_chunk_payload(
        chunk_id="chunk-1",
        pipeline_factory=lambda: pipeline,
        docstore_dict=lambda vectorstore: vectorstore.docstore._dict,
        rebuild_from_documents=lambda runtime, documents: events.append(
            ("rebuild", [doc.page_content for doc in documents])
        ),
    )

    assert payload == {
        "ok": True,
        "deleted_chunk_id": "chunk-1",
        "remaining_chunks": 1,
    }
    assert events == [("load", None), ("rebuild", ["Keep me"])]
