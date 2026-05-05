from types import SimpleNamespace

import pytest

from backend.helpers.attachment_route_helpers import (
    prepare_attachment_promotion,
    session_attachments_payload,
)
from backend.api_task_store import TaskRecord, TaskStatus


def test_session_attachments_payload_wraps_workspace_status():
    payload = session_attachments_payload(
        session_id="session-1",
        message_records=[{"id": 1}],
        preview_char_limit=4000,
        vector_store_path="vector_store_test",
        collect_attachments=lambda records, preview_char_limit: {
            "attachments": [{"attachment_id": "att-1", "kind": "file"}],
            "summary": {"total_attachments": 1},
        },
        attach_current_kb_status=lambda payload, **kwargs: {
            **payload,
            "current_vector_store_path": kwargs["vector_store_path"],
        },
        lookup_task=lambda attachment_id, vector_store_path: None,
    )

    assert payload == {
        "session_id": "session-1",
        "attachments": [{"attachment_id": "att-1", "kind": "file"}],
        "summary": {"total_attachments": 1},
        "current_vector_store_path": "vector_store_test",
    }


def test_prepare_attachment_promotion_rejects_missing_attachment():
    with pytest.raises(KeyError, match="Attachment not found"):
        prepare_attachment_promotion(
            session_id="session-1",
            attachment_id="att-1",
            attachment=None,
            target_vector_store_path="vector_store_test",
            workspace_id=None,
            existing_task=None,
            task_record_payload=lambda record, **kwargs: {},
        )


def test_prepare_attachment_promotion_rejects_invalid_attachment_states():
    with pytest.raises(ValueError, match="Only file attachments"):
        prepare_attachment_promotion(
            session_id="session-1",
            attachment_id="att-image",
            attachment={"kind": "image"},
            target_vector_store_path="vector_store_test",
            workspace_id=None,
            existing_task=None,
            task_record_payload=lambda record, **kwargs: {},
        )

    with pytest.raises(ValueError, match="downloadable content"):
        prepare_attachment_promotion(
            session_id="session-1",
            attachment_id="att-empty",
            attachment={"kind": "file", "data_url": ""},
            target_vector_store_path="vector_store_test",
            workspace_id=None,
            existing_task=None,
            task_record_payload=lambda record, **kwargs: {},
        )


def test_prepare_attachment_promotion_returns_dedupe_payload_for_existing_task():
    record = TaskRecord(
        task_id="task-1",
        task_type="promote_attachment_to_kb",
        status=TaskStatus.COMPLETED,
        params={"attachment_id": "att-1"},
        session_id="session-1",
        created_at=1.0,
        updated_at=2.0,
    )

    payload = prepare_attachment_promotion(
        session_id="session-1",
        attachment_id="att-1",
        attachment={
            "kind": "file",
            "name": "brief.txt",
            "data_url": "data:text/plain;base64,QnJpZWY=",
        },
        target_vector_store_path="vector_store_test",
        workspace_id="workspace-alpha",
        existing_task=record,
        task_record_payload=lambda record, **kwargs: {
            "task_id": record.task_id,
            "params": kwargs["params_override"],
        },
    )

    assert payload == {
        "dedupe_payload": {
            "task_id": "task-1",
            "params": {
                "attachment_id": "att-1",
                "dedupe_hit": True,
            },
        }
    }


def test_prepare_attachment_promotion_returns_enqueue_kwargs():
    payload = prepare_attachment_promotion(
        session_id="session-1",
        attachment_id="att-1",
        attachment={
            "kind": "file",
            "name": "brief.txt",
            "data_url": "data:text/plain;base64,QnJpZWY=",
        },
        target_vector_store_path="vector_store_test",
        workspace_id="workspace-alpha",
        existing_task=SimpleNamespace(status=TaskStatus.FAILED),
        task_record_payload=lambda record, **kwargs: {},
    )

    assert payload == {
        "workspace_id": "workspace-alpha",
        "dedupe_payload": None,
        "enqueue_kwargs": {
            "task_type": "promote_attachment_to_kb",
            "params": {
                "attachment_id": "att-1",
                "attachment_name": "brief.txt",
                "attachment_kind": "file",
                "attachment_data_url": "data:text/plain;base64,QnJpZWY=",
                "vector_store_path": "vector_store_test",
                "workspace_id": "workspace-alpha",
            },
            "session_id": "session-1",
        },
    }
