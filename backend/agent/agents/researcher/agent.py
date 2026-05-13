"""Research Agent implementation backed by ``search_runtime``."""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from search_runtime import run_web_research
from search_runtime.research_service import run_deep_research
from search_runtime.types import ResearchSource, WebResearchResult

from backend.agent.agents.researcher.claim_extractor import extract_atomic_claims
from backend.agent.agents.researcher.claim_verifier import verify_atomic_claims
from backend.agent.agents.researcher.archive_reuse import build_archive_reuse_context
from backend.agent.agents.researcher.contradiction import aggregate_contradictions
from backend.agent.agents.researcher.evidence_chain import (
    build_claim_evidence_chains,
    build_claim_verification_summary,
)
from backend.agent.agents.researcher.source_evaluator import evaluate_research_sources
from backend.agent.agents.researcher.synthesizer import build_research_artifact
from backend.agent.protocols import AgentResult, AgentTask

ResearchMode = Literal["quick", "deep"]
ResearchRunner = Callable[..., Awaitable[WebResearchResult]]


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _count_values(values: Sequence[str], defaults: Sequence[str]) -> dict[str, int]:
    counts = Counter(value or "unknown" for value in values)
    payload = {key: counts.get(key, 0) for key in defaults}
    for key in sorted(counts):
        if key not in payload:
            payload[key] = counts[key]
    return payload


def _claim_ids_by_status(
    evidence_chains: Sequence[dict[str, object]],
    statuses: set[str],
) -> list[str]:
    return [
        str(item.get("claim_id"))
        for item in evidence_chains
        if str(item.get("status") or "unverified") in statuses and item.get("claim_id")
    ]


def _build_delivery_action_items(
    *,
    claim_count: int,
    source_count: int,
    partial_claim_ids: list[str],
    unverified_claim_ids: list[str],
    contradiction_count: int,
    primary_source_count: int,
    unique_source_family_count: int,
    caveat_count: int,
    context_source_count: int,
    rejected_source_count: int,
) -> list[dict[str, object]]:
    """Create deterministic follow-up actions for improving deliverable quality."""
    action_items: list[dict[str, object]] = []

    if claim_count == 0:
        action_items.append(
            {
                "id": "extract_claims",
                "priority": "high",
                "description": "Extract explicit claims before treating the research as deliverable.",
            }
        )
    if source_count == 0:
        action_items.append(
            {
                "id": "collect_sources",
                "priority": "high",
                "description": "Collect supporting sources before delivery.",
            }
        )
    if unverified_claim_ids:
        action_items.append(
            {
                "id": "verify_unverified_claims",
                "priority": "high",
                "description": "Add evidence or remove unverified claims.",
                "claim_ids": unverified_claim_ids,
            }
        )
    if partial_claim_ids:
        action_items.append(
            {
                "id": "strengthen_partial_claims",
                "priority": "medium",
                "description": "Add independent evidence for partially verified claims.",
                "claim_ids": partial_claim_ids,
            }
        )
    if contradiction_count > 0:
        action_items.append(
            {
                "id": "resolve_contradictions",
                "priority": "high",
                "description": "Resolve or explicitly explain contradictory evidence.",
            }
        )
    if source_count > 0 and primary_source_count == 0:
        action_items.append(
            {
                "id": "add_primary_sources",
                "priority": "medium",
                "description": "Add primary or official sources for stronger delivery confidence.",
            }
        )
    if source_count > 0 and claim_count > 0 and unique_source_family_count < 2:
        action_items.append(
            {
                "id": "diversify_sources",
                "priority": "medium",
                "description": "Add evidence from at least one more independent source family.",
            }
        )
    if caveat_count > 0:
        action_items.append(
            {
                "id": "review_research_caveats",
                "priority": "low",
                "description": "Review provider and research caveats before final delivery.",
            }
        )
    if context_source_count > 0:
        action_items.append(
            {
                "id": "review_context_only_sources",
                "priority": "low",
                "description": "Review context-only sources before using them in a deliverable.",
            }
        )
    if rejected_source_count > 0:
        action_items.append(
            {
                "id": "replace_rejected_sources",
                "priority": "medium",
                "description": "Replace rejected low-heat sources with fresher primary or secondary evidence.",
            }
        )

    return action_items


def _build_delivery_quality_summary(
    *,
    evidence_chains: list[dict[str, object]],
    verification_summary: dict[str, object],
    evaluated_sources: list[ResearchSource],
    caveats: Sequence[str],
) -> dict[str, Any]:
    """Summarize whether a Research V2 artifact is ready for downstream delivery."""
    claim_count = len(evidence_chains)
    supported_claim_count = sum(
        1
        for item in evidence_chains
        if int(item.get("supporting_source_count") or 0) > 0
    )
    primary_supported_claim_count = sum(
        1
        for item in evidence_chains
        if bool(item.get("has_primary_source"))
    )
    verified_claim_count = int(verification_summary.get("verified_claims") or 0)
    partial_claim_count = int(verification_summary.get("partial_claims") or 0)
    unverified_claim_count = int(verification_summary.get("unverified_claims") or 0)
    contradiction_count = int(verification_summary.get("contradiction_count") or 0)
    attention_claim_ids = [
        str(item)
        for item in verification_summary.get("claims_needing_attention", [])
        if str(item or "").strip()
    ]
    partial_claim_ids = _claim_ids_by_status(evidence_chains, {"partial"})
    unverified_claim_ids = _claim_ids_by_status(evidence_chains, {"unverified"})

    source_families = sorted(
        {
            source.source_family
            for source in evaluated_sources
            if source.source_family
        }
    )
    provider_caveats = sorted(
        {
            source.provider_caveat
            for source in evaluated_sources
            if source.provider_caveat
        }
    )
    source_tier_counts = _count_values(
        [source.source_tier for source in evaluated_sources],
        ("primary", "secondary", "tertiary"),
    )
    freshness_band_counts = _count_values(
        [source.freshness_band for source in evaluated_sources],
        ("7d", "30d", "90d", "stale", "unknown"),
    )
    heat_level_counts = _count_values(
        [source.heat_level for source in evaluated_sources],
        ("hot", "warm", "cold"),
    )
    adoption_role_counts = _count_values(
        [source.adoption_role for source in evaluated_sources],
        ("evidence", "context", "rejected"),
    )

    source_count = len(evaluated_sources)
    primary_source_count = source_tier_counts.get("primary", 0)
    caveat_count = len(caveats) + len(provider_caveats)
    heat_scores = [float(source.heat_score or 0.0) for source in evaluated_sources]

    return {
        "coverage": {
            "claim_count": claim_count,
            "supported_claim_count": supported_claim_count,
            "unsupported_claim_count": max(0, claim_count - supported_claim_count),
            "verified_claim_count": verified_claim_count,
            "partial_claim_count": partial_claim_count,
            "unverified_claim_count": unverified_claim_count,
            "primary_supported_claim_count": primary_supported_claim_count,
            "source_coverage_ratio": _ratio(supported_claim_count, claim_count),
            "verification_ratio": _ratio(verified_claim_count, claim_count),
            "primary_support_ratio": _ratio(primary_supported_claim_count, claim_count),
            "attention_claim_ids": attention_claim_ids,
        },
        "source_quality": {
            "source_count": source_count,
            "source_tier_counts": source_tier_counts,
            "freshness_band_counts": freshness_band_counts,
            "heat_level_counts": heat_level_counts,
            "adoption_role_counts": adoption_role_counts,
            "average_heat_score": round(sum(heat_scores) / len(heat_scores), 4) if heat_scores else 0.0,
            "primary_source_count": primary_source_count,
            "unique_source_family_count": len(source_families),
            "source_families": source_families,
            "provider_caveat_count": len(provider_caveats),
            "research_caveat_count": len(caveats),
        },
        "action_items": _build_delivery_action_items(
            claim_count=claim_count,
            source_count=source_count,
            partial_claim_ids=partial_claim_ids,
            unverified_claim_ids=unverified_claim_ids,
            contradiction_count=contradiction_count,
            primary_source_count=primary_source_count,
            unique_source_family_count=len(source_families),
            caveat_count=caveat_count,
            context_source_count=adoption_role_counts.get("context", 0),
            rejected_source_count=adoption_role_counts.get("rejected", 0),
        ),
    }


@dataclass(slots=True)
class ResearchAgentConfig:
    mode: ResearchMode = "deep"
    providers: Sequence[str] | None = None
    max_rounds: int = 2
    max_results_per_query: int = 4
    max_fetch_pages: int = 3
    time_range: str | None = None
    allow_quick_fallback: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class DeepResearchAgent:
    """Specialized Agent for quick and deep web research workflows."""

    name = "research"
    description = "Research Agent for search, evidence collection, and deep research reports."
    capabilities = ["research", "deep_research", "web_search", "topic_research", "industry_research"]

    def __init__(
        self,
        *,
        llm: Any | None = None,
        config: ResearchAgentConfig | None = None,
        deep_runner: ResearchRunner = run_deep_research,
        quick_runner: ResearchRunner = run_web_research,
    ) -> None:
        self.llm = llm
        self.config = config or ResearchAgentConfig()
        self._deep_runner = deep_runner
        self._quick_runner = quick_runner

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(
        self,
        task: AgentTask,
        context: dict[str, Any],
    ) -> AgentResult:
        query = self._task_query(task)
        if not query:
            return self._failed_result(task, "Research task is missing a query.")

        metadata = dict(task.get("metadata") or {})
        mode = self._resolve_mode(metadata)
        providers = self._resolve_providers(metadata)
        time_range = str(metadata.get("time_range") or self.config.time_range or "").strip() or None
        max_rounds = self._resolve_int(metadata, "max_rounds", self.config.max_rounds)
        max_results = self._resolve_int(
            metadata,
            "max_results_per_query",
            self.config.max_results_per_query,
        )
        max_fetch_pages = self._resolve_int(
            metadata,
            "max_fetch_pages",
            self.config.max_fetch_pages,
        )

        try:
            if mode == "deep":
                if self.llm is None:
                    if not self.config.allow_quick_fallback:
                        return self._failed_result(task, "Deep research requires an llm instance.")
                    result = await self._quick_runner(
                        query,
                        providers=providers,
                        max_results=max_results,
                        time_range=time_range,
                    )
                    mode = "quick"
                else:
                    result = await self._deep_runner(
                        query,
                        llm=self.llm,
                        providers=providers,
                        max_rounds=max_rounds,
                        max_results_per_query=max_results,
                        time_range=time_range,
                        max_fetch_pages=max_fetch_pages,
                    )
            else:
                result = await self._quick_runner(
                    query,
                    providers=providers,
                    max_results=max_results,
                    time_range=time_range,
                )
        except Exception as exc:
            return self._failed_result(task, str(exc))

        return self._success_result(
            task,
            result,
            mode=mode,
            providers=providers,
            context=context,
        )

    def _resolve_mode(self, metadata: dict[str, Any]) -> ResearchMode:
        raw_mode = str(metadata.get("research_mode") or metadata.get("mode") or self.config.mode).strip().lower()
        return "quick" if raw_mode == "quick" else "deep"

    def _resolve_providers(self, metadata: dict[str, Any]) -> Sequence[str] | None:
        raw_providers = metadata.get("providers", self.config.providers)
        if isinstance(raw_providers, str):
            values = [item.strip() for item in raw_providers.split(",") if item.strip()]
            return values or None
        if isinstance(raw_providers, Sequence):
            values = [str(item).strip() for item in raw_providers if str(item).strip()]
            return values or None
        return None

    @staticmethod
    def _resolve_int(metadata: dict[str, Any], key: str, default: int) -> int:
        try:
            value = int(metadata.get(key, default))
        except (TypeError, ValueError):
            value = int(default)
        return max(1, value)

    @staticmethod
    def _task_query(task: AgentTask) -> str:
        raw_input = task.get("input")
        if isinstance(raw_input, str) and raw_input.strip():
            return raw_input.strip()
        description = str(task.get("description") or "").strip()
        return description

    def _failed_result(self, task: AgentTask, error: str) -> AgentResult:
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "failed",
            "output": f"Research Agent 执行失败：{error}",
            "artifacts": [],
            "sources": [],
            "error": error,
            "metadata": {"capabilities": list(self.capabilities)},
        }

    def _success_result(
        self,
        task: AgentTask,
        result: WebResearchResult,
        *,
        mode: ResearchMode,
        providers: Sequence[str] | None,
        context: dict[str, Any],
    ) -> AgentResult:
        evaluated_sources = evaluate_research_sources(
            result.sources,
            plan=result.research_plan,
            provider_caveats=result.caveats,
        )
        atomic_claims = extract_atomic_claims(result)
        verifications = verify_atomic_claims(
            atomic_claims,
            evaluated_sources,
            plan=result.research_plan,
        )
        contradictions = aggregate_contradictions(result, verifications)
        evidence_chains = build_claim_evidence_chains(
            atomic_claims,
            evaluated_sources,
            verifications,
        )
        verification_summary = build_claim_verification_summary(
            evidence_chains,
            contradictions,
        )
        delivery_quality = _build_delivery_quality_summary(
            evidence_chains=evidence_chains,
            verification_summary=verification_summary,
            evaluated_sources=evaluated_sources,
            caveats=result.caveats,
        )
        sources = [
            source.to_payload(index)
            for index, source in enumerate(evaluated_sources, start=1)
        ]
        archive_reuse = build_archive_reuse_context(context, query=result.query)
        research_artifact = build_research_artifact(
            result,
            evaluated_sources=evaluated_sources,
            atomic_claims=atomic_claims,
            verifications=verifications,
            contradictions=contradictions,
            evidence_chains=evidence_chains,
            verification_summary=verification_summary,
            reused_archives=archive_reuse,
        )
        research_artifact["delivery_quality"] = delivery_quality
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": result.to_text(max_sources=8),
            "artifacts": [
                research_artifact
            ],
            "sources": sources,
            "metadata": {
                **self.config.metadata,
                "research_mode": mode,
                "providers": list(providers or []),
                "provider_summary": result.provider_summary,
                "rewritten_query": result.rewritten_query,
                "source_count": len(result.sources),
                "atomic_claim_count": len(atomic_claims),
                "verified_claim_count": sum(1 for item in verifications if item.status == "verified"),
                "partial_claim_count": verification_summary["partial_claims"],
                "unverified_claim_count": verification_summary["unverified_claims"],
                "contradiction_count": verification_summary["contradiction_count"],
                "claim_source_coverage_ratio": delivery_quality["coverage"]["source_coverage_ratio"],
                "claim_verification_ratio": delivery_quality["coverage"]["verification_ratio"],
                "primary_source_count": delivery_quality["source_quality"]["primary_source_count"],
                "delivery_action_count": len(delivery_quality["action_items"]),
                "context_keys": sorted(context.keys()),
            },
        }


__all__ = ["DeepResearchAgent", "ResearchAgentConfig"]
