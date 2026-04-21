from backend.api_security_audit_store import SQLiteSecurityAuditStore


def test_security_audit_store_persists_and_filters_events(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteSecurityAuditStore(db_path=str(db_path), history_limit=10)

    store.append(
        {
            "timestamp": 100.0,
            "request_id": "req-1",
            "action": "get_security_status",
            "result": "ok",
            "ip": "127.0.0.1",
            "is_local": False,
            "auth_mode": "bearer",
            "auth_source": "viewer_catalog",
            "user_id": "viewer.user",
            "user_role": "viewer",
            "details": "remote_clients=True",
        }
    )
    store.append(
        {
            "timestamp": 101.0,
            "request_id": "req-2",
            "action": "remote_auth_guard",
            "result": "rejected",
            "ip": "10.0.0.8",
            "is_local": False,
            "auth_mode": "missing",
            "auth_source": "",
            "user_id": "",
            "user_role": "",
            "details": "reason=missing_token",
        }
    )

    restarted_store = SQLiteSecurityAuditStore(db_path=str(db_path), history_limit=10)
    all_events = restarted_store.list_events(limit=10)
    rejected_events = restarted_store.list_events(limit=10, result="rejected")
    status_events = restarted_store.list_events(limit=10, action="get_security_status")
    total_count = restarted_store.count_events()
    rejected_count = restarted_store.count_events(result="rejected")

    assert len(all_events) == 2
    assert [event.request_id for event in all_events] == ["req-1", "req-2"]
    assert total_count == 2
    assert len(rejected_events) == 1
    assert rejected_count == 1
    assert rejected_events[0].request_id == "req-2"
    assert len(status_events) == 1
    assert status_events[0].auth_source == "viewer_catalog"


def test_security_audit_store_prunes_old_events(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteSecurityAuditStore(db_path=str(db_path), history_limit=3)

    for index in range(5):
        store.append(
            {
                "timestamp": float(index + 1),
                "request_id": f"req-{index}",
                "action": "probe",
                "result": "ok",
                "ip": "127.0.0.1",
                "is_local": True,
                "auth_mode": "local",
                "auth_source": "local_bypass",
                "user_id": "local",
                "user_role": "admin",
                "details": f"index={index}",
            }
        )

    events = store.list_events(limit=10)

    assert len(events) == 3
    assert [event.request_id for event in events] == ["req-2", "req-3", "req-4"]


def test_security_audit_store_trim_to_latest_supports_manual_cleanup(tmp_path):
    db_path = tmp_path / "chat_history.db"
    store = SQLiteSecurityAuditStore(db_path=str(db_path), history_limit=10)

    for index in range(4):
        store.append(
            {
                "timestamp": float(index + 1),
                "request_id": f"req-{index}",
                "action": "probe",
                "result": "ok",
                "ip": "127.0.0.1",
                "is_local": True,
                "auth_mode": "local",
                "auth_source": "local_bypass",
                "user_id": "local",
                "user_role": "admin",
                "details": f"index={index}",
            }
        )

    deleted_keep_tail = store.trim_to_latest(2)
    remaining_after_tail = store.list_events(limit=10)
    deleted_clear_all = store.trim_to_latest(0)

    assert deleted_keep_tail == 2
    assert [event.request_id for event in remaining_after_tail] == ["req-2", "req-3"]
    assert deleted_clear_all == 2
    assert store.count_events() == 0
