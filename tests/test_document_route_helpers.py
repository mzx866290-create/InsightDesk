import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.document_route_helpers import (
    document_stats_payload,
    upload_documents_result,
)


class _AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def test_upload_documents_result_creates_task_and_audits():
    tasks = {}
    calls = []
    audits = []
    request = SimpleNamespace(name="request")
    record = SimpleNamespace(task_id="task-1", created_at=123.0)

    async def stage_upload_files(files, **kwargs):
        calls.append(("stage", files, kwargs))
        return ["tmp/a.pdf"], ["a.pdf"]

    async def dispatch_existing_task_record(task_record):
        calls.append(("dispatch", task_record.task_id))
        return "inline"

    result = asyncio.run(
        upload_documents_result(
            request=request,
            files=["file"],
            vector_store_path="kb",
            effective_vector_store_path=lambda path: f"resolved:{path}",
            stage_upload_files=stage_upload_files,
            build_upload_documents_task_record=lambda **kwargs: record,
            resolve_tasks=lambda: tasks,
            tasks_lock=_AsyncLock(),
            prune_task_records_locked=lambda created_at: calls.append(
                ("prune-memory", created_at)
            ),
            persist_task_record=lambda task_record: calls.append(
                ("persist", task_record.task_id)
            ),
            prune_persisted_tasks=lambda: calls.append(("prune-persisted",)),
            dispatch_existing_task_record=dispatch_existing_task_record,
            logger=SimpleNamespace(
                info=lambda *args, **kwargs: calls.append(("log-info", args)),
                exception=lambda *args, **kwargs: calls.append(("log-exception", args)),
            ),
            audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
            upload_documents_response=lambda task_record, **kwargs: {
                "task_id": task_record.task_id,
                **kwargs,
            },
            cleanup_temp_paths=lambda temp_paths: calls.append(
                ("cleanup", temp_paths)
            ),
            document_upload_max_count=3,
            document_upload_max_file_bytes=100,
            document_upload_max_total_bytes=300,
        )
    )

    assert result == {
        "task_id": "task-1",
        "file_count": 1,
        "vector_store_path": "resolved:kb",
    }
    assert tasks == {"task-1": record}
    assert calls == [
        (
            "stage",
            ["file"],
            {
                "max_file_count": 3,
                "max_file_bytes": 100,
                "max_total_bytes": 300,
            },
        ),
        ("prune-memory", 123.0),
        ("persist", "task-1"),
        ("prune-persisted",),
        ("dispatch", "task-1"),
        (
            "log-info",
            ("task_id=%s task_type=upload_documents created", "task-1"),
        ),
    ]
    assert audits == [
        (
            ("upload_documents", request),
            {"details": "file_count=1 vector_store_path=resolved:kb"},
        )
    ]


def test_upload_documents_result_cleans_staged_files_on_validation_error():
    calls = []
    audits = []

    async def stage_upload_files(files, **kwargs):
        return ["tmp/b.pdf"], ["b.pdf"]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_documents_result(
                request="request",
                files=["file"],
                vector_store_path=None,
                effective_vector_store_path=lambda path: "resolved",
                stage_upload_files=stage_upload_files,
                build_upload_documents_task_record=lambda **kwargs: (
                    (_ for _ in ()).throw(ValueError("bad upload"))
                ),
                resolve_tasks=lambda: {},
                tasks_lock=_AsyncLock(),
                prune_task_records_locked=lambda created_at: None,
                persist_task_record=lambda task_record: None,
                prune_persisted_tasks=lambda: None,
                dispatch_existing_task_record=lambda task_record: None,
                logger=SimpleNamespace(info=lambda *args, **kwargs: None),
                audit_security_event=lambda *args, **kwargs: audits.append(
                    (args, kwargs)
                ),
                upload_documents_response=lambda task_record, **kwargs: {},
                cleanup_temp_paths=lambda temp_paths: calls.append(
                    ("cleanup", temp_paths)
                ),
                document_upload_max_count=3,
                document_upload_max_file_bytes=100,
                document_upload_max_total_bytes=300,
            )
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "bad upload"
    assert calls == [("cleanup", ["tmp/b.pdf"])]
    assert audits == [
        (
            ("upload_documents", "request"),
            {"result": "rejected", "details": "bad upload"},
        )
    ]


def test_upload_documents_result_cleans_staged_files_on_unexpected_error():
    calls = []

    async def stage_upload_files(files, **kwargs):
        return ["tmp/c.pdf"], ["c.pdf"]

    async def dispatch_existing_task_record(task_record):
        raise RuntimeError("queue failed")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_documents_result(
                request="request",
                files=["file"],
                vector_store_path=None,
                effective_vector_store_path=lambda path: "resolved",
                stage_upload_files=stage_upload_files,
                build_upload_documents_task_record=lambda **kwargs: SimpleNamespace(
                    task_id="task-2",
                    created_at=456.0,
                ),
                resolve_tasks=lambda: {},
                tasks_lock=_AsyncLock(),
                prune_task_records_locked=lambda created_at: None,
                persist_task_record=lambda task_record: None,
                prune_persisted_tasks=lambda: None,
                dispatch_existing_task_record=dispatch_existing_task_record,
                logger=SimpleNamespace(
                    info=lambda *args, **kwargs: None,
                    exception=lambda *args, **kwargs: calls.append(
                        ("log-exception", args)
                    ),
                ),
                audit_security_event=lambda *args, **kwargs: None,
                upload_documents_response=lambda task_record, **kwargs: {},
                cleanup_temp_paths=lambda temp_paths: calls.append(
                    ("cleanup", temp_paths)
                ),
                document_upload_max_count=3,
                document_upload_max_file_bytes=100,
                document_upload_max_total_bytes=300,
            )
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "queue failed"
    assert calls == [
        ("cleanup", ["tmp/c.pdf"]),
        ("log-exception", ("Document upload failed",)),
    ]


def test_document_stats_payload_loads_pipeline_and_audits():
    audits = []

    class Pipeline:
        def __init__(self, vector_store_path):
            self.vector_store_path = vector_store_path

        def load_store(self):
            self.loaded = True

        def get_stats(self):
            return {"documents": 2}

    payload = document_stats_payload(
        request="request",
        path="kb",
        effective_vector_store_path=lambda path: f"resolved:{path}",
        doc_pipeline_factory=Pipeline,
        audit_security_event=lambda *args, **kwargs: audits.append((args, kwargs)),
    )

    assert payload == {"documents": 2, "store_path": "resolved:kb"}
    assert audits == [
        (
            ("get_document_stats", "request"),
            {"details": "path=resolved:kb"},
        )
    ]


def test_document_stats_payload_maps_pipeline_errors_to_500():
    class Pipeline:
        vector_store_path = "resolved"

        def __init__(self, vector_store_path):
            self.vector_store_path = vector_store_path

        def load_store(self):
            raise RuntimeError("load failed")

    with pytest.raises(HTTPException) as exc:
        document_stats_payload(
            request="request",
            path=None,
            effective_vector_store_path=lambda path: "resolved",
            doc_pipeline_factory=Pipeline,
            audit_security_event=lambda *args, **kwargs: None,
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "load failed"
