import json
import logging
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.task_approval_policy_helpers import (
    DEFAULT_TASK_APPROVAL_POLICY,
    TASK_APPROVAL_POLICY_CONFIG_KEY,
    load_task_approval_policy_payload,
    normalize_task_approval_policy,
    save_task_approval_policy_payload,
)


class MemoryConfigStore:
    def __init__(self) -> None:
        self.records: dict[str, SimpleNamespace] = {}

    def get(self, key: str):
        return self.records.get(key)

    def set(self, key: str, value: str):
        record = SimpleNamespace(value=value, updated_at=123.0)
        self.records[key] = record
        return record


def test_normalize_task_approval_policy_deduplicates_task_types_and_defaults_role():
    assert normalize_task_approval_policy(
        {
            "enabled": True,
            "required_task_types": ["writing", " ", "research", "writing"],
            "high_risk_requires_approval": False,
            "default_reviewer_role": "",
            "updated_at": 12.5,
        }
    ) == {
        "enabled": True,
        "required_task_types": ["writing", "research"],
        "high_risk_requires_approval": False,
        "default_reviewer_role": "admin",
        "updated_at": 12.5,
    }


def test_normalize_task_approval_policy_rejects_too_many_task_types():
    with pytest.raises(HTTPException) as exc_info:
        normalize_task_approval_policy(
            {"required_task_types": [f"task-{index}" for index in range(21)]}
        )

    assert exc_info.value.status_code == 400


def test_load_task_approval_policy_payload_returns_default_when_missing_or_invalid(caplog):
    store = MemoryConfigStore()
    logger = logging.getLogger("task-approval-policy-test")

    assert load_task_approval_policy_payload(store, logger) == DEFAULT_TASK_APPROVAL_POLICY

    store.records[TASK_APPROVAL_POLICY_CONFIG_KEY] = SimpleNamespace(
        value="{bad-json",
        updated_at=99.0,
    )
    with caplog.at_level(logging.WARNING, logger=logger.name):
        assert load_task_approval_policy_payload(store, logger) == DEFAULT_TASK_APPROVAL_POLICY

    assert "Stored task approval policy is not valid JSON" in caplog.text


def test_save_task_approval_policy_payload_persists_compact_json_without_updated_at():
    store = MemoryConfigStore()

    payload = save_task_approval_policy_payload(
        store,
        {
            "enabled": True,
            "required_task_types": ["writing"],
            "updated_at": 99.0,
        },
    )

    assert payload == {
        "enabled": True,
        "required_task_types": ["writing"],
        "high_risk_requires_approval": True,
        "default_reviewer_role": "admin",
        "updated_at": 123.0,
    }
    stored = json.loads(store.records[TASK_APPROVAL_POLICY_CONFIG_KEY].value)
    assert stored == {
        "enabled": True,
        "required_task_types": ["writing"],
        "high_risk_requires_approval": True,
        "default_reviewer_role": "admin",
    }
