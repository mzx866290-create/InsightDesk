import time

from api_task_store import RESTART_FAILURE_MESSAGE, SQLiteTaskStore, TaskRecord, TaskStatus
from chat_store import connect_sqlite


def test_task_store_marks_incomplete_tasks_failed_after_restart(tmp_path):
    db_path = tmp_path / "chat_history.db"

    store = SQLiteTaskStore(db_path=str(db_path))
    store.save(
        TaskRecord(
            task_id="pending-task",
            task_type="upload_documents",
            status=TaskStatus.PENDING,
            params={},
            session_id=None,
            created_at=1.0,
            updated_at=1.0,
            progress=25,
        )
    )

    restarted_store = SQLiteTaskStore(db_path=str(db_path))
    reloaded = restarted_store.get("pending-task")

    assert reloaded is not None
    assert reloaded.status == TaskStatus.FAILED
    assert reloaded.error == RESTART_FAILURE_MESSAGE


def test_task_store_prune_enforces_terminal_history_limit(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteTaskStore(db_path=str(db_path), history_limit=1, ttl_seconds=999999)
    now = time.time()

    store.save(
        TaskRecord(
            task_id="done-old",
            task_type="demo",
            status=TaskStatus.COMPLETED,
            params={},
            session_id=None,
            created_at=now - 2,
            updated_at=now - 2,
            progress=100,
        )
    )
    store.save(
        TaskRecord(
            task_id="done-new",
            task_type="demo",
            status=TaskStatus.COMPLETED,
            params={},
            session_id=None,
            created_at=now - 1,
            updated_at=now - 1,
            progress=100,
        )
    )
    store.save(
        TaskRecord(
            task_id="running",
            task_type="demo",
            status=TaskStatus.RUNNING,
            params={},
            session_id=None,
            created_at=now,
            updated_at=now,
            progress=50,
        )
    )

    store.prune()

    assert store.get("done-old") is None
    assert store.get("done-new") is not None
    assert store.get("running") is not None


def test_task_store_attachment_promotion_lookup_survives_task_row_cleanup(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteTaskStore(db_path=str(db_path))
    record = TaskRecord(
        task_id="promotion-task",
        task_type="promote_attachment_to_kb",
        status=TaskStatus.COMPLETED,
        params={
            "attachment_id": "att-brief",
            "attachment_name": "brief.txt",
            "vector_store_path": "vector_store_test",
        },
        session_id="session-1",
        created_at=5.0,
        updated_at=7.0,
        result="indexed",
        progress=100,
    )
    store.save(record)

    with connect_sqlite(str(db_path)) as conn:
        conn.execute("DELETE FROM tasks WHERE task_id = ?", (record.task_id,))
        conn.commit()

    recovered = store.get_attachment_promotion_task("att-brief", "vector_store_test")

    assert recovered is not None
    assert recovered.task_id == "promotion-task"
    assert recovered.status == TaskStatus.COMPLETED
    assert recovered.result == "indexed"
    assert recovered.params["attachment_id"] == "att-brief"


def test_task_store_list_recent_orders_by_updated_at(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteTaskStore(db_path=str(db_path))

    store.save(
        TaskRecord(
            task_id="older-created-newer-updated",
            task_type="demo",
            status=TaskStatus.RUNNING,
            params={},
            session_id=None,
            created_at=1.0,
            updated_at=20.0,
            progress=80,
        )
    )
    store.save(
        TaskRecord(
            task_id="newer-created-older-updated",
            task_type="demo",
            status=TaskStatus.COMPLETED,
            params={},
            session_id=None,
            created_at=10.0,
            updated_at=15.0,
            progress=100,
        )
    )

    records = store.list_recent(limit=5)

    assert [record.task_id for record in records[:2]] == [
        "older-created-newer-updated",
        "newer-created-older-updated",
    ]


def test_task_store_delete_for_session_removes_records_and_temp_files(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteTaskStore(db_path=str(db_path))
    temp_file = tmp_path / "upload.tmp"
    temp_file.write_text("temporary", encoding="utf-8")

    store.save(
        TaskRecord(
            task_id="upload-task",
            task_type="upload_documents",
            status=TaskStatus.RUNNING,
            params={"temp_paths": [str(temp_file)]},
            session_id="session-cleanup",
            created_at=1.0,
            updated_at=2.0,
            progress=25,
        )
    )
    store.save(
        TaskRecord(
            task_id="promotion-task",
            task_type="promote_attachment_to_kb",
            status=TaskStatus.COMPLETED,
            params={
                "attachment_id": "att-cleanup",
                "attachment_name": "brief.txt",
                "vector_store_path": "vector_store_test",
            },
            session_id="session-cleanup",
            created_at=3.0,
            updated_at=4.0,
            progress=100,
        )
    )

    result = store.delete_for_session("session-cleanup")

    assert result == {"tasks": 2, "attachment_promotions": 1}
    assert store.get("upload-task") is None
    assert store.get("promotion-task") is None
    assert store.get_attachment_promotion("att-cleanup", "vector_store_test") is None
    assert not temp_file.exists()
