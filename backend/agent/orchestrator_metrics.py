"""Runtime metrics helpers for the multi-agent orchestrator."""

from __future__ import annotations

from typing import Any

from backend.agent.protocols import AgentResult, AgentTask
from backend.agent.state import OrchestratorAgentMetric

_COST_PER_MILLION_TOKENS_USD: dict[tuple[str, str], dict[str, float]] = {
    ("anthropic", "claude-3-5-haiku-latest"): {"prompt": 0.8, "completion": 4.0},
    ("anthropic", "claude-3-5-sonnet-latest"): {"prompt": 3.0, "completion": 15.0},
    ("anthropic", "claude-3-7-sonnet-latest"): {"prompt": 3.0, "completion": 15.0},
    ("openai", "gpt-4.1"): {"prompt": 2.0, "completion": 8.0},
    ("openai", "gpt-4.1-mini"): {"prompt": 0.4, "completion": 1.6},
    ("openai", "gpt-4.1-nano"): {"prompt": 0.1, "completion": 0.4},
    ("openai", "gpt-4o"): {"prompt": 2.5, "completion": 10.0},
    ("openai", "gpt-4o-mini"): {"prompt": 0.15, "completion": 0.6},
    ("openai", "gpt-5"): {"prompt": 1.25, "completion": 10.0},
    ("openai", "gpt-5-mini"): {"prompt": 0.25, "completion": 2.0},
    ("openai", "gpt-5-nano"): {"prompt": 0.05, "completion": 0.4},
}


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _optional_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().lower()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _extract_token_usage(metadata: dict[str, Any]) -> dict[str, int]:
    usage = metadata.get("usage") or metadata.get("token_usage") or metadata.get("llm_usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    prompt_tokens = _non_negative_int(
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or metadata.get("prompt_tokens")
        or metadata.get("input_tokens")
    )
    completion_tokens = _non_negative_int(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or metadata.get("completion_tokens")
        or metadata.get("output_tokens")
    )
    total_tokens = _non_negative_int(
        usage.get("total_tokens")
        or metadata.get("total_tokens")
        or (prompt_tokens + completion_tokens)
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _cost_override(metadata: dict[str, Any]) -> dict[str, float]:
    for key in ("cost_per_million_tokens_usd", "cost_per_1m_tokens_usd", "pricing"):
        raw_pricing = metadata.get(key)
        if isinstance(raw_pricing, dict):
            prompt = _optional_float(
                raw_pricing.get("prompt")
                or raw_pricing.get("input")
                or raw_pricing.get("prompt_tokens")
                or raw_pricing.get("input_tokens")
            )
            completion = _optional_float(
                raw_pricing.get("completion")
                or raw_pricing.get("output")
                or raw_pricing.get("completion_tokens")
                or raw_pricing.get("output_tokens")
            )
            if prompt or completion:
                return {"prompt": prompt, "completion": completion}
    return {}


def _lookup_token_pricing(metadata: dict[str, Any]) -> tuple[str, str, dict[str, float]]:
    provider = _first_non_empty(
        metadata.get("provider"),
        metadata.get("llm_provider"),
        metadata.get("model_provider"),
    )
    model = _first_non_empty(
        metadata.get("model"),
        metadata.get("model_name"),
        metadata.get("model_id"),
    )

    override = _cost_override(metadata)
    if override:
        return provider, model, override

    pricing = _COST_PER_MILLION_TOKENS_USD.get(
        (_normalize_label(provider), _normalize_label(model)),
        {},
    )
    return provider, model, pricing


def _estimate_cost_from_tokens(
    metadata: dict[str, Any],
    token_usage: dict[str, int],
) -> tuple[float, str, str, str]:
    provider, model, pricing = _lookup_token_pricing(metadata)
    if not pricing:
        return 0.0, provider, model, "none"

    prompt_cost = token_usage["prompt_tokens"] * _optional_float(pricing.get("prompt")) / 1_000_000
    completion_cost = (
        token_usage["completion_tokens"]
        * _optional_float(pricing.get("completion"))
        / 1_000_000
    )
    return prompt_cost + completion_cost, provider, model, "override" if _cost_override(metadata) else "table"


def build_agent_metric(
    task: AgentTask,
    agent_name: str,
    result: AgentResult | None,
    *,
    duration_ms: int,
    status: str,
    error: str = "",
    trace_id: str = "",
    span_id: str = "",
) -> OrchestratorAgentMetric:
    result_payload = result or {}
    metadata = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
    task_metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    merged_metadata = {**task_metadata, **metadata}
    token_usage = _extract_token_usage(metadata)
    usage_cost = 0
    for usage_key in ("usage", "token_usage", "llm_usage"):
        usage_payload = metadata.get(usage_key)
        if isinstance(usage_payload, dict):
            usage_cost = usage_payload.get("estimated_cost_usd") or usage_payload.get("cost_usd") or 0
            if usage_cost:
                break
    mapped_cost, provider, model, cost_source = _estimate_cost_from_tokens(
        merged_metadata,
        token_usage,
    )
    direct_cost = metadata.get("estimated_cost_usd") or metadata.get("cost_usd") or usage_cost
    estimated_cost_usd = _optional_float(direct_cost or mapped_cost)
    resolved_cost_source = "none"
    if estimated_cost_usd:
        resolved_cost_source = "metadata" if direct_cost else cost_source
    artifacts = result_payload.get("artifacts")
    sources = result_payload.get("sources")
    used_llm = bool(metadata.get("used_llm") or token_usage["total_tokens"] > 0 or estimated_cost_usd > 0)

    return {
        "step_id": str(task.get("id") or ""),
        "agent": str(result_payload.get("agent") or agent_name or ""),
        "task_type": str(result_payload.get("task_type") or task.get("type") or ""),
        "status": str(result_payload.get("status") or status or ""),
        "trace_id": trace_id,
        "span_id": span_id,
        "duration_ms": max(0, int(duration_ms)),
        "artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
        "source_count": len(sources) if isinstance(sources, list) else 0,
        "used_llm": used_llm,
        "prompt_tokens": token_usage["prompt_tokens"],
        "completion_tokens": token_usage["completion_tokens"],
        "total_tokens": token_usage["total_tokens"],
        "estimated_cost_usd": round(estimated_cost_usd, 6),
        "error": error,
        "metadata": {
            "result_metadata_keys": sorted(str(key) for key in metadata.keys()),
            "cost_source": resolved_cost_source,
            "provider": provider,
            "model": model,
            "candidate_count": _non_negative_int(metadata.get("candidate_count")),
            "selected_panel_id": str(metadata.get("selected_panel_id") or ""),
            "selected_model_id": str(metadata.get("selected_model_id") or ""),
            "synthesis_strategy": str(metadata.get("synthesis_strategy") or ""),
        },
    }


def summarize_agent_metrics(
    metrics: dict[str, OrchestratorAgentMetric],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "step_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "total_duration_ms": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "agents": {},
    }
    for metric in metrics.values():
        agent = str(metric.get("agent") or "agent")
        agent_summary = summary["agents"].setdefault(
            agent,
            {
                "step_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "total_duration_ms": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "artifact_count": 0,
                "source_count": 0,
            },
        )
        status = str(metric.get("status") or "")
        duration_ms = _non_negative_int(metric.get("duration_ms"))
        total_tokens = _non_negative_int(metric.get("total_tokens"))
        estimated_cost = _optional_float(metric.get("estimated_cost_usd"))

        summary["step_count"] += 1
        summary["completed_count"] += 1 if status == "completed" else 0
        summary["failed_count"] += 1 if status == "failed" else 0
        summary["total_duration_ms"] += duration_ms
        summary["total_tokens"] += total_tokens
        summary["estimated_cost_usd"] += estimated_cost

        agent_summary["step_count"] += 1
        agent_summary["completed_count"] += 1 if status == "completed" else 0
        agent_summary["failed_count"] += 1 if status == "failed" else 0
        agent_summary["total_duration_ms"] += duration_ms
        agent_summary["total_tokens"] += total_tokens
        agent_summary["estimated_cost_usd"] += estimated_cost
        agent_summary["artifact_count"] += _non_negative_int(metric.get("artifact_count"))
        agent_summary["source_count"] += _non_negative_int(metric.get("source_count"))

    summary["estimated_cost_usd"] = round(float(summary["estimated_cost_usd"]), 6)
    for agent_summary in summary["agents"].values():
        agent_summary["estimated_cost_usd"] = round(float(agent_summary["estimated_cost_usd"]), 6)
    return summary


__all__ = ["build_agent_metric", "summarize_agent_metrics"]
