from types import SimpleNamespace

import pytest

from backend.helpers.workflow_task_payload_helpers import (
    build_multi_agent_workflow_task_params,
)


class ModelDumpPanelConfig:
    def model_dump(self, *, mode: str):
        assert mode == "json"
        return {"provider": "qiny", "model": "qwen"}


def test_build_multi_agent_workflow_task_params_validates_user_request_before_policy_load():
    policy_loader_called = False

    def policy_loader():
        nonlocal policy_loader_called
        policy_loader_called = True
        return {"enabled": True}

    with pytest.raises(ValueError, match="Workflow user_request cannot be empty"):
        build_multi_agent_workflow_task_params(
            SimpleNamespace(user_request=" "),
            task_approval_policy_loader=policy_loader,
        )

    assert policy_loader_called is False


def test_build_multi_agent_workflow_task_params_normalizes_fields_and_injects_policy():
    request = SimpleNamespace(
        user_request="  Draft a report  ",
        session_id="session-1",
        panel_id=" panel-1 ",
        answer_group_id=" answer-1 ",
        model_id=" ",
        context={},
        plan=[{"agent": "writing"}],
        research_mode=" DEEP ",
        research_source_strategy=" WEB_ONLY ",
        providers=[" google ", "", "bing"],
        max_rounds=0,
        max_results_per_query=0,
        max_fetch_pages=0,
        time_range=" week ",
        use_kb_context=True,
        vector_store_path=" kb/path ",
        allow_quick_fallback=True,
        data_files=[],
        panel_config=ModelDumpPanelConfig(),
    )

    params = build_multi_agent_workflow_task_params(
        request,
        task_approval_policy_loader=lambda: {
            "enabled": True,
            "required_task_types": ["writing"],
        },
    )

    assert params["user_request"] == "Draft a report"
    assert params["model_id"] == "multi_agent_workflow"
    assert params["context"] == {
        "session_id": "session-1",
        "task_approval_policy": {
            "enabled": True,
            "required_task_types": ["writing"],
        },
    }
    assert params["providers"] == ["google", "bing"]
    assert params["max_rounds"] == 2
    assert params["max_results_per_query"] == 4
    assert params["max_fetch_pages"] == 3
    assert params["panel_config"] == {"provider": "qiny", "model": "qwen"}


def test_build_multi_agent_workflow_task_params_adds_data_file_summary_and_analysis_step():
    request = SimpleNamespace(
        user_request="Analyze the CSV",
        context={},
        data_files=[
            {
                "name": "sample.csv",
                "extracted_text": "region,revenue\nNorth,120\nSouth,180",
            }
        ],
        plan=[{"agent": "writing"}],
    )

    params = build_multi_agent_workflow_task_params(request)

    assert params["context"]["rows"] == [
        {"region": "North", "revenue": "120"},
        {"region": "South", "revenue": "180"},
    ]
    assert params["data_files"] == [{"name": "sample.csv", "row_count": 2}]
    assert [step["agent"] for step in params["plan"]] == [
        "data_analysis",
        "writing",
    ]
