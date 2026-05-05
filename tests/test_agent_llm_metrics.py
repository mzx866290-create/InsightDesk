import asyncio
from types import SimpleNamespace

import pytest

from backend.agent.llm import _ainvoke_llm_with_timeout, _astream_llm_with_timeout
from backend.agent.orchestrator_metrics import build_agent_metric
from backend.core.runtime_metrics import (
    reset_runtime_llm_metrics,
    runtime_llm_metrics_payload,
)


class FakeLLM:
    provider = "test-provider"
    model = "test-model"

    async def ainvoke(self, payload):
        return SimpleNamespace(
            content=f"ok:{payload}",
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 3,
                    "total_tokens": 5,
                }
            },
        )


class FakeStreamingLLM:
    provider = "test-provider"
    model = "stream-model"

    async def astream(self, payload):
        yield SimpleNamespace(content="hello")
        yield SimpleNamespace(content=f" {payload}")


class SlowLLM:
    provider = "test-provider"
    model = "slow-model"

    async def ainvoke(self, payload):
        await asyncio.sleep(0.05)
        return SimpleNamespace(content="late")


def test_ainvoke_llm_with_timeout_records_success_metrics():
    reset_runtime_llm_metrics()

    response = asyncio.run(_ainvoke_llm_with_timeout(FakeLLM(), "payload", timeout_seconds=1))
    payload = runtime_llm_metrics_payload()

    assert response.content == "ok:payload"
    assert payload["total_calls"] == 1
    assert payload["total_errors"] == 0
    assert payload["prompt_tokens"] == 2
    assert payload["completion_tokens"] == 3
    assert payload["total_tokens"] == 5
    assert payload["by_model"][0]["provider"] == "test-provider"
    assert payload["by_model"][0]["model"] == "test-model"


def test_astream_llm_with_timeout_records_stream_metrics():
    reset_runtime_llm_metrics()

    async def collect():
        chunks = []
        async for chunk in _astream_llm_with_timeout(
            FakeStreamingLLM(),
            "stream",
            timeout_seconds=1,
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(collect())
    payload = runtime_llm_metrics_payload()

    assert chunks == ["hello", " stream"]
    assert payload["total_calls"] == 1
    assert payload["total_errors"] == 0
    assert payload["by_model"][0]["model"] == "stream-model"


def test_ainvoke_llm_with_timeout_records_timeout_metrics():
    reset_runtime_llm_metrics()

    with pytest.raises(TimeoutError):
        asyncio.run(_ainvoke_llm_with_timeout(SlowLLM(), "payload", timeout_seconds=0.001))

    payload = runtime_llm_metrics_payload()
    assert payload["total_calls"] == 1
    assert payload["total_errors"] == 1
    assert payload["total_timeouts"] == 1
    assert payload["by_model"][0]["total_timeouts"] == 1


def test_orchestrator_metric_estimates_cost_from_provider_model_mapping():
    metric = build_agent_metric(
        {
            "id": "step-cost",
            "type": "research",
            "description": "Cost mapping",
            "metadata": {},
        },
        "research",
        {
            "agent": "research",
            "task_type": "research",
            "status": "completed",
            "artifacts": [],
            "sources": [],
            "metadata": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "usage": {
                    "prompt_tokens": 1_000_000,
                    "completion_tokens": 1_000_000,
                },
            },
        },
        duration_ms=10,
        status="completed",
    )

    assert metric["total_tokens"] == 2_000_000
    assert metric["estimated_cost_usd"] == 0.75
    assert metric["metadata"]["cost_source"] == "table"
    assert metric["metadata"]["provider"] == "openai"
    assert metric["metadata"]["model"] == "gpt-4o-mini"


def test_orchestrator_metric_prefers_metadata_cost_and_supports_task_pricing_override():
    legacy_metric = build_agent_metric(
        {"id": "legacy", "type": "writing", "description": "Legacy", "metadata": {}},
        "writing",
        {
            "agent": "writing",
            "status": "completed",
            "artifacts": [],
            "sources": [],
            "metadata": {
                "estimated_cost_usd": 1.23,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        },
        duration_ms=1,
        status="completed",
    )
    override_metric = build_agent_metric(
        {
            "id": "override",
            "type": "writing",
            "description": "Override",
            "metadata": {
                "provider": "custom-provider",
                "model": "custom-model",
                "cost_per_million_tokens_usd": {"prompt": 2.0, "completion": 4.0},
            },
        },
        "writing",
        {
            "agent": "writing",
            "status": "completed",
            "artifacts": [],
            "sources": [],
            "metadata": {
                "usage": {"prompt_tokens": 500_000, "completion_tokens": 250_000},
            },
        },
        duration_ms=1,
        status="completed",
    )

    assert legacy_metric["estimated_cost_usd"] == 1.23
    assert legacy_metric["metadata"]["cost_source"] == "metadata"
    assert override_metric["estimated_cost_usd"] == 2.0
    assert override_metric["metadata"]["cost_source"] == "override"


def test_orchestrator_metric_exposes_model_compare_preference_metadata():
    metric = build_agent_metric(
        {"id": "compare", "type": "model_compare", "description": "Compare", "metadata": {}},
        "model_compare",
        {
            "agent": "model_compare",
            "task_type": "model_compare",
            "status": "completed",
            "artifacts": [{"type": "model_compare_synthesis"}],
            "sources": [],
            "metadata": {
                "candidate_count": 3,
                "selected_panel_id": "panel-b",
                "selected_model_id": "model-b",
                "synthesis_strategy": "deterministic_weighted_preference_synthesis",
            },
        },
        duration_ms=12,
        status="completed",
    )

    assert metric["metadata"]["candidate_count"] == 3
    assert metric["metadata"]["selected_panel_id"] == "panel-b"
    assert metric["metadata"]["selected_model_id"] == "model-b"
    assert metric["metadata"]["synthesis_strategy"] == "deterministic_weighted_preference_synthesis"
