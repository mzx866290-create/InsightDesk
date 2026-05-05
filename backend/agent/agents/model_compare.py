"""Model comparison Agent with evaluation repository and preference synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.agent.protocols import AgentResult, AgentTask


_DEFAULT_PREFERENCE_WEIGHTS: dict[str, float] = {
    "source_count": 1.5,
    "artifact_count": 0.8,
    "completed_workflow_count": 1.2,
    "content_depth": 0.015,
    "required_term_coverage": 4.0,
    "preferred_term_match": 1.0,
    "avoid_term_penalty": 2.0,
    "preference_bonus": 2.0,
}


@dataclass(slots=True)
class ModelCompareAgentConfig:
    """Runtime knobs for deterministic model comparison."""

    preference_weights: dict[str, float] = field(default_factory=dict)
    preference_contract: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelCompareAgent:
    """Compare parallel model outputs and synthesize the preferred answer."""

    name = "model_compare"
    description = "Model Compare Agent for multi-model evaluation, preference scoring, and synthesis."
    capabilities = ["model_compare", "compare_models", "synthesis", "preference", "evaluation"]

    def __init__(self, *, config: ModelCompareAgentConfig | None = None) -> None:
        self.config = config or ModelCompareAgentConfig()

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        candidates = _collect_candidates(task, context)
        weights = {**_DEFAULT_PREFERENCE_WEIGHTS, **dict(self.config.preference_weights or {})}
        preferred_panel_id = _first_text(
            task.get("metadata", {}).get("preferred_panel_id")
            if isinstance(task.get("metadata"), dict)
            else "",
            context.get("preferred_panel_id"),
            context.get("selected_panel_id"),
        )
        preferred_model_id = _first_text(
            task.get("metadata", {}).get("preferred_model_id")
            if isinstance(task.get("metadata"), dict)
            else "",
            context.get("preferred_model_id"),
            context.get("selected_model_id"),
        )
        preference_contract = _merge_preference_contract(
            self.config.preference_contract,
            context.get("preference_contract"),
            context.get("evaluation_contract"),
            _mapping_value(task.get("input"), "preference_contract"),
            _mapping_value(task.get("input"), "evaluation_contract"),
            task.get("metadata", {}).get("preference_contract")
            if isinstance(task.get("metadata"), dict)
            else {},
            task.get("metadata", {}).get("evaluation_contract")
            if isinstance(task.get("metadata"), dict)
            else {},
        )
        evaluation_repository = build_evaluation_repository(
            candidates,
            weights=weights,
            preferred_panel_id=preferred_panel_id,
            preferred_model_id=preferred_model_id,
            preference_contract=preference_contract,
        )
        synthesis = synthesize_model_comparison(
            evaluation_repository,
            user_request=str(task.get("description") or task.get("input") or ""),
        )
        selected = evaluation_repository["ranking"][0] if evaluation_repository["ranking"] else {}

        output = _render_output(evaluation_repository, synthesis)
        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": output,
            "artifacts": [
                {
                    "type": "model_evaluation_repository",
                    "title": "Model comparison evaluation repository",
                    "content": evaluation_repository,
                },
                {
                    "type": "model_preference",
                    "title": "Preference model decision",
                    "content": evaluation_repository["preference_model"],
                },
                {
                    "type": "model_compare_synthesis",
                    "title": "Synthesized model comparison answer",
                    "content": synthesis,
                },
            ],
            "sources": _dedupe_sources(candidates),
            "metadata": {
                **dict(self.config.metadata or {}),
                "candidate_count": len(candidates),
                "selected_panel_id": str(selected.get("panel_id") or ""),
                "selected_model_id": str(selected.get("model_id") or ""),
                "synthesis_strategy": synthesis["strategy"],
                "used_llm": False,
            },
        }


def build_evaluation_repository(
    candidates: list[dict[str, Any]],
    *,
    weights: dict[str, float] | None = None,
    preferred_panel_id: str = "",
    preferred_model_id: str = "",
    preference_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_weights = {**_DEFAULT_PREFERENCE_WEIGHTS, **dict(weights or {})}
    resolved_contract = _merge_preference_contract(preference_contract)
    normalized_candidates = [
        _score_candidate(
            item,
            resolved_weights,
            preferred_panel_id,
            preferred_model_id,
            resolved_contract,
        )
        for item in candidates
    ]
    normalized_candidates.sort(
        key=lambda item: (
            item["contract_evaluation"]["contract_satisfied"],
            item["score"],
            item["source_count"],
            item["artifact_count"],
            item["content_length"],
            item["panel_id"],
        ),
        reverse=True,
    )

    comparisons: list[dict[str, Any]] = []
    winner = normalized_candidates[0] if normalized_candidates else {}
    for candidate in normalized_candidates[1:]:
        comparisons.append(
            {
                "winner_panel_id": str(winner.get("panel_id") or ""),
                "challenger_panel_id": candidate["panel_id"],
                "score_gap": round(float(winner.get("score") or 0.0) - candidate["score"], 4),
                "winner_advantages": _candidate_advantages(winner, candidate),
                "challenger_advantages": _candidate_advantages(candidate, winner),
            }
        )

    preference_model = {
        "name": "deterministic_weighted_preference_v1",
        "weights": resolved_weights,
        "preferred_panel_id": preferred_panel_id,
        "preferred_model_id": preferred_model_id,
        "selected_panel_id": str(winner.get("panel_id") or ""),
        "selected_model_id": str(winner.get("model_id") or ""),
        "selected_score": float(winner.get("score") or 0.0),
        "preference_contract": resolved_contract,
        "selected_contract_satisfied": bool(
            winner.get("contract_evaluation", {}).get("contract_satisfied")
            if isinstance(winner.get("contract_evaluation"), dict)
            else False
        ),
        "selected_missing_required_terms": list(
            winner.get("contract_evaluation", {}).get("missing_required_terms", [])
            if isinstance(winner.get("contract_evaluation"), dict)
            else []
        ),
        "selection_reasons": _selection_reasons(winner),
        "candidate_count": len(normalized_candidates),
    }
    return {
        "version": 1,
        "candidate_count": len(normalized_candidates),
        "criteria": list(resolved_weights.keys()),
        "preference_model": preference_model,
        "evaluation_matrix": _build_evaluation_matrix(normalized_candidates, resolved_weights),
        "ranking": normalized_candidates,
        "comparisons": comparisons,
        "consensus_points": _build_consensus_points(normalized_candidates),
        "difference_points": _build_difference_points(normalized_candidates),
    }


def synthesize_model_comparison(
    evaluation_repository: dict[str, Any],
    *,
    user_request: str = "",
) -> dict[str, Any]:
    ranking = [
        item
        for item in evaluation_repository.get("ranking", [])
        if isinstance(item, dict)
    ]
    winner = ranking[0] if ranking else {}
    consensus_terms = [
        str(item.get("term") or "")
        for item in evaluation_repository.get("consensus_points", [])
        if isinstance(item, dict) and str(item.get("term") or "").strip()
    ][:6]
    difference_notes = [
        str(item.get("note") or "")
        for item in evaluation_repository.get("difference_points", [])
        if isinstance(item, dict) and str(item.get("note") or "").strip()
    ][:4]
    winner_content = _clip_text(winner.get("content"), 1200)
    preference_model = (
        evaluation_repository.get("preference_model")
        if isinstance(evaluation_repository.get("preference_model"), dict)
        else {}
    )
    selection_reasons = [
        str(item or "").strip()
        for item in preference_model.get("selection_reasons", [])
        if str(item or "").strip()
    ][:4]
    synthesis_inputs = [
        {
            "panel_id": str(item.get("panel_id") or ""),
            "model_id": str(item.get("model_id") or ""),
            "rank": index + 1,
            "score": float(item.get("score") or 0.0),
            "contract_satisfied": bool(
                item.get("contract_evaluation", {}).get("contract_satisfied")
                if isinstance(item.get("contract_evaluation"), dict)
                else False
            ),
            "excerpt": _clip_text(item.get("content"), 320),
        }
        for index, item in enumerate(ranking[:3])
    ]

    sections: list[str] = ["# Synthesized Answer"]
    if user_request:
        sections.append(f"Request: {_clip_text(user_request, 240)}")
    if winner_content:
        sections.append(winner_content)
    if selection_reasons:
        sections.append("Selected because: " + "; ".join(selection_reasons) + ".")
    if consensus_terms:
        sections.append("Consensus signals: " + ", ".join(consensus_terms) + ".")
    if difference_notes:
        sections.append("Model-specific additions: " + " ".join(difference_notes))
    if not winner_content:
        sections.append("No substantive model output was available to synthesize.")

    return {
        "answer": "\n\n".join(sections).strip(),
        "source_panel_id": str(winner.get("panel_id") or ""),
        "source_model_id": str(winner.get("model_id") or ""),
        "source_panel_ids": [item["panel_id"] for item in synthesis_inputs if item["panel_id"]],
        "synthesis_inputs": synthesis_inputs,
        "merged_candidate_count": len(synthesis_inputs),
        "strategy": "deterministic_weighted_preference_synthesis",
        "consensus_terms": consensus_terms,
        "difference_notes": difference_notes,
        "selection_reasons": selection_reasons,
        "preference_contract": dict(preference_model.get("preference_contract") or {}),
        "estimated": False,
    }


def _collect_candidates(task: AgentTask, context: dict[str, Any]) -> list[dict[str, Any]]:
    task_metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    raw_candidates = _first_list(
        _mapping_list(task.get("input"), "candidates"),
        task_metadata.get("candidates"),
        context.get("model_candidates"),
        context.get("candidates"),
    )
    candidates = [_normalize_candidate(item, index) for index, item in enumerate(raw_candidates)]
    if candidates:
        return candidates

    upstream = context.get("_agent_results") if isinstance(context.get("_agent_results"), dict) else {}
    return [
        _candidate_from_agent_result(step_id, result)
        for step_id, result in upstream.items()
        if isinstance(result, dict) and str(result.get("output") or "").strip()
    ]


def _normalize_candidate(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {"content": str(raw or "")}
    content = _first_text(raw.get("content"), raw.get("output"), raw.get("answer"), raw.get("text"))
    panel_id = _first_text(raw.get("panel_id"), raw.get("id"), raw.get("candidate_id"), f"candidate-{index + 1}")
    return {
        "panel_id": panel_id,
        "model_id": _first_text(raw.get("model_id"), raw.get("model"), raw.get("agent"), panel_id),
        "provider": _first_text(raw.get("provider"), raw.get("llm_provider")),
        "content": content,
        "sources": [item for item in raw.get("sources", []) if isinstance(item, dict)],
        "artifacts": [item for item in raw.get("artifacts", []) if isinstance(item, dict)],
        "metadata": dict(raw.get("metadata") or {}),
    }


def _candidate_from_agent_result(step_id: str, result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    return {
        "panel_id": str(step_id or result.get("task_id") or result.get("agent") or "candidate"),
        "model_id": _first_text(metadata.get("model"), metadata.get("model_id"), result.get("agent")),
        "provider": _first_text(metadata.get("provider"), metadata.get("llm_provider")),
        "content": str(result.get("output") or ""),
        "sources": [item for item in result.get("sources", []) if isinstance(item, dict)],
        "artifacts": [item for item in result.get("artifacts", []) if isinstance(item, dict)],
        "metadata": metadata,
    }


def _score_candidate(
    candidate: dict[str, Any],
    weights: dict[str, float],
    preferred_panel_id: str,
    preferred_model_id: str,
    preference_contract: dict[str, Any],
) -> dict[str, Any]:
    content = str(candidate.get("content") or "")
    source_count = len(candidate.get("sources") or [])
    artifact_count = len(candidate.get("artifacts") or [])
    completed_workflow_count = _completed_workflow_count(candidate)
    content_length = len(content)
    contract_evaluation = _evaluate_preference_contract(content, preference_contract)
    score = (
        source_count * weights["source_count"]
        + artifact_count * weights["artifact_count"]
        + completed_workflow_count * weights["completed_workflow_count"]
        + min(content_length, 1600) * weights["content_depth"]
        + contract_evaluation["required_term_coverage"] * weights["required_term_coverage"]
        + len(contract_evaluation["matched_preferred_terms"]) * weights["preferred_term_match"]
        - len(contract_evaluation["matched_avoid_terms"]) * weights["avoid_term_penalty"]
    )
    if preferred_panel_id and str(candidate.get("panel_id") or "") == preferred_panel_id:
        score += weights["preference_bonus"]
    if preferred_model_id and str(candidate.get("model_id") or "") == preferred_model_id:
        score += weights["preference_bonus"]

    return {
        **candidate,
        "source_count": source_count,
        "artifact_count": artifact_count,
        "completed_workflow_count": completed_workflow_count,
        "content_length": content_length,
        "score": round(score, 4),
        "terms": _extract_terms(content),
        "contract_evaluation": contract_evaluation,
    }


def _completed_workflow_count(candidate: dict[str, Any]) -> int:
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
    value = metadata.get("completed_workflow_count") or metadata.get("completed_steps") or 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _build_evaluation_matrix(
    candidates: list[dict[str, Any]],
    weights: dict[str, float],
) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for rank, candidate in enumerate(candidates, start=1):
        criteria = {
            "source_count": {
                "value": int(candidate.get("source_count") or 0),
                "weight": weights["source_count"],
                "weighted_score": round(int(candidate.get("source_count") or 0) * weights["source_count"], 4),
            },
            "artifact_count": {
                "value": int(candidate.get("artifact_count") or 0),
                "weight": weights["artifact_count"],
                "weighted_score": round(int(candidate.get("artifact_count") or 0) * weights["artifact_count"], 4),
            },
            "completed_workflow_count": {
                "value": int(candidate.get("completed_workflow_count") or 0),
                "weight": weights["completed_workflow_count"],
                "weighted_score": round(
                    int(candidate.get("completed_workflow_count") or 0)
                    * weights["completed_workflow_count"],
                    4,
                ),
            },
            "content_depth": {
                "value": min(int(candidate.get("content_length") or 0), 1600),
                "weight": weights["content_depth"],
                "weighted_score": round(
                    min(int(candidate.get("content_length") or 0), 1600)
                    * weights["content_depth"],
                    4,
                ),
            },
        }
        contract_evaluation = (
            candidate.get("contract_evaluation")
            if isinstance(candidate.get("contract_evaluation"), dict)
            else {}
        )
        criteria["required_term_coverage"] = {
            "value": float(contract_evaluation.get("required_term_coverage") or 0.0),
            "weight": weights["required_term_coverage"],
            "weighted_score": round(
                float(contract_evaluation.get("required_term_coverage") or 0.0)
                * weights["required_term_coverage"],
                4,
            ),
            "matched_terms": list(contract_evaluation.get("matched_required_terms") or []),
            "missing_terms": list(contract_evaluation.get("missing_required_terms") or []),
        }
        criteria["preferred_term_match"] = {
            "value": len(contract_evaluation.get("matched_preferred_terms") or []),
            "weight": weights["preferred_term_match"],
            "weighted_score": round(
                len(contract_evaluation.get("matched_preferred_terms") or [])
                * weights["preferred_term_match"],
                4,
            ),
            "matched_terms": list(contract_evaluation.get("matched_preferred_terms") or []),
        }
        criteria["avoid_term_penalty"] = {
            "value": len(contract_evaluation.get("matched_avoid_terms") or []),
            "weight": weights["avoid_term_penalty"],
            "weighted_score": round(
                -len(contract_evaluation.get("matched_avoid_terms") or [])
                * weights["avoid_term_penalty"],
                4,
            ),
            "matched_terms": list(contract_evaluation.get("matched_avoid_terms") or []),
        }
        matrix.append(
            {
                "rank": rank,
                "panel_id": str(candidate.get("panel_id") or ""),
                "model_id": str(candidate.get("model_id") or ""),
                "score": float(candidate.get("score") or 0.0),
                "criteria": criteria,
            }
        )
    return matrix


def _build_consensus_points(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(candidates) < 2:
        return []
    term_panels: dict[str, list[str]] = {}
    for candidate in candidates:
        panel_id = str(candidate.get("panel_id") or "")
        for term in candidate.get("terms", []):
            panels = term_panels.setdefault(term, [])
            if panel_id and panel_id not in panels:
                panels.append(panel_id)
    threshold = max(2, (len(candidates) + 1) // 2)
    consensus = [
        {"term": term, "support_count": len(panel_ids), "panel_ids": panel_ids}
        for term, panel_ids in term_panels.items()
        if len(panel_ids) >= threshold
    ]
    consensus.sort(key=lambda item: (-item["support_count"], item["term"]))
    return consensus[:8]


def _build_difference_points(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    term_counts: dict[str, int] = {}
    for candidate in candidates:
        for term in set(candidate.get("terms", [])):
            term_counts[term] = term_counts.get(term, 0) + 1

    differences: list[dict[str, Any]] = []
    for candidate in candidates:
        unique_terms = [
            term
            for term in candidate.get("terms", [])
            if term_counts.get(term, 0) == 1
        ][:5]
        if not unique_terms:
            continue
        panel_id = str(candidate.get("panel_id") or "")
        differences.append(
            {
                "panel_id": panel_id,
                "model_id": str(candidate.get("model_id") or ""),
                "unique_terms": unique_terms,
                "note": f"{panel_id} adds {', '.join(unique_terms[:3])}.",
            }
        )
    return differences[:8]


def _candidate_advantages(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    advantages: list[str] = []
    if int(left.get("source_count") or 0) > int(right.get("source_count") or 0):
        advantages.append("more source support")
    if int(left.get("artifact_count") or 0) > int(right.get("artifact_count") or 0):
        advantages.append("more structured artifacts")
    if int(left.get("content_length") or 0) > int(right.get("content_length") or 0):
        advantages.append("deeper answer coverage")
    left_contract = left.get("contract_evaluation") if isinstance(left.get("contract_evaluation"), dict) else {}
    right_contract = right.get("contract_evaluation") if isinstance(right.get("contract_evaluation"), dict) else {}
    if bool(left_contract.get("contract_satisfied")) and not bool(right_contract.get("contract_satisfied")):
        advantages.append("satisfies preference contract")
    if len(left_contract.get("matched_preferred_terms") or []) > len(
        right_contract.get("matched_preferred_terms") or []
    ):
        advantages.append("matches more preferred terms")
    return advantages


def _selection_reasons(winner: dict[str, Any]) -> list[str]:
    if not winner:
        return []
    reasons: list[str] = []
    contract_evaluation = (
        winner.get("contract_evaluation")
        if isinstance(winner.get("contract_evaluation"), dict)
        else {}
    )
    if contract_evaluation.get("contract_satisfied"):
        matched_required = list(contract_evaluation.get("matched_required_terms") or [])
        if matched_required:
            reasons.append("satisfied required terms: " + ", ".join(matched_required[:4]))
        elif contract_evaluation.get("required_terms") or contract_evaluation.get("avoid_terms"):
            reasons.append("satisfied the preference contract")
    matched_preferred = list(contract_evaluation.get("matched_preferred_terms") or [])
    if matched_preferred:
        reasons.append("matched preferred terms: " + ", ".join(matched_preferred[:4]))
    if int(winner.get("source_count") or 0) > 0:
        reasons.append(f"used {int(winner.get('source_count') or 0)} source(s)")
    if int(winner.get("artifact_count") or 0) > 0:
        reasons.append(f"returned {int(winner.get('artifact_count') or 0)} artifact(s)")
    reasons.append(f"ranked highest with score {float(winner.get('score') or 0.0):.4f}")
    return reasons[:5]


def _evaluate_preference_contract(content: str, contract: dict[str, Any]) -> dict[str, Any]:
    required_terms = list(contract.get("required_terms") or [])
    preferred_terms = list(contract.get("preferred_terms") or [])
    avoid_terms = list(contract.get("avoid_terms") or [])
    matched_required = [term for term in required_terms if _term_in_content(term, content)]
    missing_required = [term for term in required_terms if term not in matched_required]
    matched_preferred = [term for term in preferred_terms if _term_in_content(term, content)]
    matched_avoid = [term for term in avoid_terms if _term_in_content(term, content)]
    required_coverage = len(matched_required) / len(required_terms) if required_terms else 0.0
    minimum_coverage = float(contract.get("minimum_required_coverage") or 1.0)
    required_terms_satisfied = (
        required_coverage >= minimum_coverage
        if required_terms
        else True
    )
    return {
        "required_terms": required_terms,
        "matched_required_terms": matched_required,
        "missing_required_terms": missing_required,
        "required_term_coverage": round(required_coverage, 4),
        "preferred_terms": preferred_terms,
        "matched_preferred_terms": matched_preferred,
        "avoid_terms": avoid_terms,
        "matched_avoid_terms": matched_avoid,
        "minimum_required_coverage": minimum_coverage,
        "contract_satisfied": required_terms_satisfied and not matched_avoid,
    }


def _term_in_content(term: str, content: str) -> bool:
    normalized_term = str(term or "").strip().lower()
    normalized_content = str(content or "").lower()
    if not normalized_term:
        return False
    if re.fullmatch(r"[A-Za-z0-9_-]+", normalized_term):
        return re.search(rf"\b{re.escape(normalized_term)}\b", normalized_content) is not None
    return normalized_term in normalized_content


def _merge_preference_contract(*values: Any) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "name": "deterministic_preference_contract_v1",
        "required_terms": [],
        "preferred_terms": [],
        "avoid_terms": [],
        "minimum_required_coverage": 1.0,
    }
    for raw in values:
        if not isinstance(raw, dict):
            continue
        if _first_text(raw.get("name")):
            contract["name"] = _first_text(raw.get("name"))
        for key in ("required_terms", "preferred_terms", "avoid_terms"):
            existing = list(contract[key])
            for term in _normalize_contract_terms(raw.get(key)):
                if term not in existing:
                    existing.append(term)
            contract[key] = existing
        if "minimum_required_coverage" in raw:
            contract["minimum_required_coverage"] = _clamped_float(
                raw.get("minimum_required_coverage"),
                default=1.0,
                minimum=0.0,
                maximum=1.0,
            )
    return contract


def _normalize_contract_terms(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    raw_items: list[Any]
    if isinstance(value, str):
        raw_items = [item.strip() for item in re.split(r"[,;\n]", value)]
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    terms: list[str] = []
    for item in raw_items:
        term = str(item or "").strip().lower()
        if term and term not in terms:
            terms.append(term)
    return terms


def _clamped_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _render_output(evaluation_repository: dict[str, Any], synthesis: dict[str, Any]) -> str:
    selected = evaluation_repository["preference_model"]["selected_panel_id"]
    candidate_count = evaluation_repository["candidate_count"]
    return "\n\n".join(
        [
            "# Model Compare Agent Synthesis",
            f"Selected: {selected or 'none'} from {candidate_count} candidates.",
            str(synthesis.get("answer") or ""),
        ]
    ).strip()


def _dedupe_sources(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []
    for candidate in candidates:
        for source in candidate.get("sources", []):
            key = "|".join(
                [
                    str(source.get("url") or ""),
                    str(source.get("title") or ""),
                    str(source.get("type") or ""),
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            sources.append(dict(source))
    return sources


def _extract_terms(text: Any) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", str(text or "").lower())
    ignored = {"that", "this", "with", "from", "have", "will", "into", "your", "model"}
    terms: list[str] = []
    for word in words:
        if word in ignored or word in terms:
            continue
        terms.append(word)
        if len(terms) >= 18:
            break
    return terms


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _first_list(*values: Any) -> list[Any]:
    for value in values:
        if isinstance(value, list) and value:
            return value
    return []


def _mapping_list(value: Any, key: str) -> list[Any]:
    if isinstance(value, dict) and isinstance(value.get(key), list):
        return list(value[key])
    return []


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _clip_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


__all__ = [
    "ModelCompareAgent",
    "ModelCompareAgentConfig",
    "build_evaluation_repository",
    "synthesize_model_comparison",
]
