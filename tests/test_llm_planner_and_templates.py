"""Workflow template storage and LLM planner unit tests."""

from __future__ import annotations

import asyncio
import json
import types

from backend.agent.llm_planner import (
    build_llm_plan,
    llm_planner_enabled,
    normalize_planned_task_types,
    plan_task_types_with_llm,
)
from backend.helpers import workflow_template_helpers as wth


class _Registry:
    def find_for_task(self, task_type: str):
        if task_type == "research":
            return types.SimpleNamespace(name="research")
        if task_type == "writing":
            return types.SimpleNamespace(name="writer")
        return types.SimpleNamespace(name="general")


class _FakeLLM:
    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, prompt: str):
        return types.SimpleNamespace(content=self._content)


def test_llm_planner_disabled_by_default_and_context_overrides():
    assert llm_planner_enabled({}) is False
    assert llm_planner_enabled({"use_llm_planner": True}) is True
    assert llm_planner_enabled({"use_llm_planner": False}) is False


def test_llm_planner_env_flag_enables(tmp_path, monkeypatch):
    monkeypatch.delenv("WORKFLOW_LLM_PLANNER", raising=False)
    assert llm_planner_enabled(None) is False
    monkeypatch.setenv("WORKFLOW_LLM_PLANNER", "1")
    assert llm_planner_enabled(None) is True


def test_normalize_planned_task_types_dedupes_and_filters():
    assert normalize_planned_task_types(
        ["research", "writing", "research", "made_up_type"]
    ) == ["research", "writing"]
    assert normalize_planned_task_types("research") is None
    assert normalize_planned_task_types(["made_up"]) is None


def test_plan_task_types_with_llm_parses_json_and_falls_back():
    good = _FakeLLM('{"task_types": ["research", "writing"]}')
    assert asyncio.run(plan_task_types_with_llm("req", good)) == ["research", "writing"]

    bad = _FakeLLM("sorry, I cannot answer in JSON")
    assert asyncio.run(plan_task_types_with_llm("req", bad)) is None

    assert asyncio.run(plan_task_types_with_llm("req", None)) is None


def test_build_llm_plan_tags_steps_with_llm_planner():
    plan = asyncio.run(build_llm_plan("调研并撰写报告", _FakeLLM(
        '{"task_types": ["research", "writing"]}'
    ), _Registry()))

    assert plan is not None and len(plan) == 2
    assert [step["task_type"] for step in plan] == ["research", "writing"]
    assert [step["agent"] for step in plan] == ["research", "writer"]
    assert all(step["metadata"]["planner"] == "llm" for step in plan)


def test_workflow_template_roundtrip(tmp_path):
    project_root = tmp_path
    record = wth.save_workflow_template(
        {
            "name": "调研写作流",
            "description": "research then write",
            "plan": [
                {"task_type": "research", "agent": "research"},
                {"task_type": "writing", "agent": "writer", "requires_approval": True},
            ],
        },
        project_root=project_root,
    )
    assert record["template_id"]
    assert len(record["plan"]) == 2

    templates = wth.list_workflow_templates(project_root)
    assert [item["template_id"] for item in templates] == [record["template_id"]]

    fetched = wth.get_workflow_template(record["template_id"], project_root)
    assert fetched is not None and fetched["name"] == "调研写作流"

    assert wth.delete_workflow_template(record["template_id"], project_root) is True
    assert wth.list_workflow_templates(project_root) == []
    assert wth.delete_workflow_template(record["template_id"], project_root) is False


def test_workflow_template_requires_name_and_plan(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        wth.save_workflow_template({"name": " ", "plan": []}, project_root=tmp_path)
    with pytest.raises(ValueError):
        wth.save_workflow_template({"name": "x", "plan": []}, project_root=tmp_path)


def test_workflow_template_survives_reload(tmp_path):
    wth.save_workflow_template(
        {"name": "t1", "plan": [{"task_type": "general"}]}, project_root=tmp_path
    )
    raw = json.loads((tmp_path / "runtime" / "workflow_templates.json").read_text("utf-8"))
    assert raw[0]["name"] == "t1"
