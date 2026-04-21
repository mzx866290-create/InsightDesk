from typing import Any, Callable

from backend.api_task_store import TaskRecord, TaskStatus


def session_attachments_payload(
    *,
    session_id: str,
    message_records: list[dict[str, Any]],
    preview_char_limit: int,
    vector_store_path: str,
    collect_attachments: Callable[..., dict[str, Any]],
    attach_current_kb_status: Callable[..., dict[str, Any]],
    lookup_task: Callable[[str, str], TaskRecord | None],
) -> dict[str, Any]:
    payload = collect_attachments(
        message_records,
        preview_char_limit=preview_char_limit,
    )
    payload = attach_current_kb_status(
        payload,
        vector_store_path=vector_store_path,
        lookup_task=lookup_task,
    )
    return {
        "session_id": session_id,
        **payload,
    }


def prepare_attachment_promotion(
    *,
    session_id: str,
    attachment_id: str,
    attachment: dict[str, Any] | None,
    target_vector_store_path: str,
    workspace_id: str | None = None,
    existing_task: TaskRecord | None,
    task_record_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if not attachment:
        raise KeyError("Attachment not found")

    if str(attachment.get("kind") or "").strip() != "file":
        raise ValueError("Only file attachments can be promoted to the knowledge base.")

    data_url = str(attachment.get("data_url") or "").strip()
    if not data_url:
        raise ValueError("This attachment no longer has downloadable content.")

    if existing_task and existing_task.status in {
        TaskStatus.PENDING,
        TaskStatus.RUNNING,
        TaskStatus.COMPLETED,
    }:
        params = dict(existing_task.params)
        params["dedupe_hit"] = True
        return {
            "dedupe_payload": task_record_payload(
                existing_task,
                params_override=params,
            )
        }

    return {
        "workspace_id": str(workspace_id or "").strip() or None,
        "dedupe_payload": None,
        "enqueue_kwargs": {
            "task_type": "promote_attachment_to_kb",
            "params": {
                "attachment_id": attachment_id,
                "attachment_name": str(attachment.get("name") or "").strip(),
                "attachment_kind": "file",
                "attachment_data_url": data_url,
                "vector_store_path": target_vector_store_path,
                **(
                    {"workspace_id": str(workspace_id or "").strip()}
                    if str(workspace_id or "").strip()
                    else {}
                ),
            },
            "session_id": session_id,
        },
    }
