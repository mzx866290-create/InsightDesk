"""Session helper utilities."""

import hashlib
import json
import re
import time
from html import escape
from typing import Any, Callable


_SHARED_SLIDE_TYPE_LABELS = {
    "cover": "Cover",
    "agenda": "Agenda",
    "section": "Section",
    "content": "Content",
    "summary": "Summary",
    "closing": "Closing",
}

_SHARED_QUALITY_LABELS = {
    "supported": "Evidence supported",
    "manual": "Needs manual review",
    "draft": "Draft",
}

_SHARED_THEME_LABELS = {
    "default": "经典蓝图",
    "midnight": "深夜简报",
    "sunrise": "晨曦回顾",
}

_SHARED_SOURCE_MODE_LABELS = {
    "kb_plus_chat": "知识库 + 聊天",
    "chat_only": "仅聊天",
}

_REVIEW_TERM_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}")
_REVIEW_TERM_STOPWORDS = {
    "about",
    "after",
    "also",
    "answer",
    "because",
    "before",
    "could",
    "from",
    "have",
    "into",
    "more",
    "need",
    "needs",
    "option",
    "should",
    "that",
    "their",
    "there",
    "this",
    "with",
    "would",
    "一个",
    "以及",
    "可以",
    "如果",
    "当前",
    "建议",
    "需要",
    "因此",
    "进行",
}


def _content_hash(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        payload = value
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clip_text(text: Any, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if limit <= 0 or len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 3)].rstrip() + "..."


def _base_model_payload(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


def _clip_attachment_preview_text(text: str, limit: int) -> str:
    collapsed = re.sub(r"\s+", " ", str(text or "")).strip()
    if limit <= 0 or len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(1, limit - 3)].rstrip() + "..."


def _extract_review_terms(content: Any, *, limit: int = 24) -> list[str]:
    text = str(content or "").lower()
    terms: list[str] = []
    seen: set[str] = set()
    for match in _REVIEW_TERM_PATTERN.finditer(text):
        term = re.sub(r"[_-]+", " ", match.group(0)).strip()
        if not term or term in _REVIEW_TERM_STOPWORDS:
            continue
        if len(term) < 3 and not re.fullmatch(r"[\u4e00-\u9fff]{2,}", term):
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) >= limit:
            break
    return terms


def _safe_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _estimate_token_count(text: Any) -> int:
    normalized = str(text or "").strip()
    if not normalized:
        return 0
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    non_cjk_chars = len(re.sub(r"[\u4e00-\u9fff\s]", "", normalized))
    # Conservative deterministic estimate used only when provider usage is absent.
    return max(1, cjk_chars + ((non_cjk_chars + 3) // 4))


def _usage_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _extract_candidate_token_usage(
    candidate: dict[str, Any],
    *,
    prompt_text: str,
) -> dict[str, Any]:
    usage_candidates: list[dict[str, Any]] = []
    for key in ("token_usage", "usage", "llm_usage"):
        usage = _usage_mapping(candidate.get(key))
        if usage:
            usage_candidates.append(usage)

    metadata = _usage_mapping(candidate.get("metadata"))
    for key in ("token_usage", "usage", "llm_usage"):
        usage = _usage_mapping(metadata.get(key))
        if usage:
            usage_candidates.append(usage)
    if metadata:
        usage_candidates.append(metadata)

    for usage in usage_candidates:
        prompt_tokens = _safe_non_negative_int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or usage.get("prompt_eval_count")
        )
        completion_tokens = _safe_non_negative_int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or usage.get("eval_count")
        )
        total_tokens = _safe_non_negative_int(
            usage.get("total_tokens")
            or usage.get("total_token_count")
            or (prompt_tokens + completion_tokens)
        )
        if prompt_tokens or completion_tokens or total_tokens:
            if total_tokens < prompt_tokens + completion_tokens:
                total_tokens = prompt_tokens + completion_tokens
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated": False,
                "estimation_method": "",
            }

    prompt_tokens = _estimate_token_count(prompt_text)
    completion_tokens = _estimate_token_count(candidate.get("content"))
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated": True,
        "estimation_method": "character_count_cjk_aware",
    }


def _shared_slide_type_label(value: Any) -> str:
    normalized = str(value or "").strip()
    return _SHARED_SLIDE_TYPE_LABELS.get(normalized, normalized or "Content")


def _shared_quality_label(value: Any) -> str:
    normalized = str(value or "").strip()
    return _SHARED_QUALITY_LABELS.get(normalized, normalized or "Draft")


def _shared_theme_label(value: Any) -> str:
    normalized = str(value or "").strip()
    return _SHARED_THEME_LABELS.get(normalized, normalized or "经典蓝图")


def _shared_source_mode_label(value: Any) -> str:
    normalized = str(value or "").strip()
    return _SHARED_SOURCE_MODE_LABELS.get(normalized, normalized or "仅聊天")


def message_payload(record: dict[str, Any]) -> dict[str, Any]:
    role = "user" if record.get("type") == "human" else "assistant"
    payload = {
        "id": record.get("id"),
        "role": role,
        "content": record.get("content", ""),
        "images": record.get("images", []),
        "files": record.get("files", []),
        "sources": record.get("sources", []),
        "model_id": record.get("model_id", ""),
        "panel_id": record.get("panel_id", ""),
        "answer_group_id": record.get("answer_group_id", ""),
        "workflow_nodes": record.get("workflow_nodes", []),
        "task_id": record.get("task_id", ""),
        "task_type": record.get("task_type", ""),
        "feedback_value": record.get("feedback_value", 0),
        "timestamp": float(record.get("timestamp") or 0),
    }
    token_usage = dict(record.get("token_usage") or {})
    if token_usage:
        payload["token_usage"] = token_usage
    return payload


AnswerGroupReviewer = Callable[[dict[str, Any]], dict[str, Any] | None]
_answer_group_reviewer: AnswerGroupReviewer | None = None


def set_answer_group_reviewer(reviewer: AnswerGroupReviewer | None) -> None:
    global _answer_group_reviewer
    _answer_group_reviewer = reviewer


def _score_answer_candidate(
    candidate: dict[str, Any],
    *,
    is_primary: bool,
    prompt_text: str = "",
) -> dict[str, Any]:
    content = str(candidate.get("content") or "").strip()
    sources = [item for item in candidate.get("sources", []) if isinstance(item, dict)]
    workflow_nodes = [
        item for item in candidate.get("workflow_nodes", []) if isinstance(item, dict)
    ]
    completed_workflow_nodes = [
        item
        for item in workflow_nodes
        if str(item.get("status") or "").strip().lower() == "completed"
    ]

    content_length = len(content)
    token_usage = _extract_candidate_token_usage(candidate, prompt_text=prompt_text)
    source_count = len(sources)
    workflow_count = len(workflow_nodes)
    completed_workflow_count = len(completed_workflow_nodes)

    score = 0.0
    score_breakdown: dict[str, float] = {}
    strengths: list[str] = []
    concerns: list[str] = []

    def add_score(reason: str, delta: float) -> None:
        nonlocal score
        score += delta
        if delta:
            score_breakdown[reason] = round(score_breakdown.get(reason, 0.0) + delta, 2)

    if content_length >= 240:
        add_score("content_depth", 3.0)
        strengths.append("Expanded answer coverage")
    elif content_length >= 120:
        add_score("content_depth", 2.0)
        strengths.append("Substantial answer detail")
    elif content_length >= 40:
        add_score("content_depth", 1.0)
    else:
        add_score("brevity_penalty", -2.0)
        concerns.append("Answer is too brief")

    if source_count > 0:
        add_score("source_support", min(6.0, source_count * 2.0))
        strengths.append(f"Uses {source_count} supporting sources")
    else:
        concerns.append("No supporting sources attached")

    if completed_workflow_count > 0:
        add_score("workflow_trace", min(3.0, float(completed_workflow_count)))
        strengths.append(f"Shows {completed_workflow_count} completed workflow steps")
    elif workflow_count > 0:
        add_score("workflow_trace", 0.5)
        strengths.append("Includes workflow execution trace")

    if candidate.get("task_type"):
        add_score("task_alignment", 0.5)

    if re.search(r"(\n[-*\u2022]\s)|(\d+\.\s)", content):
        add_score("structured_delivery", 0.5)
        strengths.append("Structured response format")

    if re.search(
        r"(鎬荤粨|缁撹|寤鸿|涓嬩竴姝椋庨櫓|鎺ㄨ崘|summary|conclusion|recommend)",
        content,
        re.IGNORECASE,
    ):
        add_score("decision_readiness", 0.5)
        strengths.append("Clear decision-oriented framing")

    if is_primary:
        add_score("primary_panel_bias", 0.1)

    return {
        "panel_id": str(candidate.get("panel_id") or ""),
        "model_id": str(candidate.get("model_id") or ""),
        "content": content,
        "excerpt": _clip_text(content, 180),
        "source_count": source_count,
        "workflow_node_count": workflow_count,
        "completed_workflow_count": completed_workflow_count,
        "content_length": content_length,
        "token_usage": token_usage,
        "timestamp": float(candidate.get("timestamp") or 0),
        "score": round(score, 2),
        "score_breakdown": score_breakdown,
        "strengths": strengths,
        "concerns": concerns,
        "is_primary_panel": bool(is_primary),
    }


def _review_factor_details(
    factor_key: str,
    winner: dict[str, Any],
    other: dict[str, Any],
) -> tuple[str, float, str] | None:
    factor_labels = {
        "source_support": "evidence support",
        "workflow_trace": "workflow trace",
        "content_depth": "answer depth",
        "structured_delivery": "structured delivery",
        "decision_readiness": "decision readiness",
        "task_alignment": "task alignment",
        "brevity_penalty": "brevity risk",
        "primary_panel_bias": "primary panel bias",
    }
    label = factor_labels.get(factor_key, factor_key.replace("_", " "))
    winner_value = float(winner.get("score_breakdown", {}).get(factor_key, 0.0))
    other_value = float(other.get("score_breakdown", {}).get(factor_key, 0.0))
    delta = round(winner_value - other_value, 2)
    if abs(delta) < 0.01:
        return None

    if factor_key == "brevity_penalty":
        if winner_value > other_value:
            detail = (
                f"{winner['panel_id']} avoids short-answer penalties better than {other['panel_id']}."
            )
        else:
            detail = (
                f"{winner['panel_id']} carries more brevity risk than {other['panel_id']}."
            )
    elif delta > 0:
        detail = f"{winner['panel_id']} is stronger on {label}."
    else:
        detail = f"{winner['panel_id']} trails {other['panel_id']} on {label}."
    return label, delta, detail


def _build_candidate_comparison(
    winner: dict[str, Any],
    other: dict[str, Any],
) -> dict[str, Any]:
    factor_keys = {
        *winner.get("score_breakdown", {}).keys(),
        *other.get("score_breakdown", {}).keys(),
    }
    factor_deltas = [
        details
        for details in (
            _review_factor_details(factor_key, winner, other)
            for factor_key in sorted(factor_keys)
        )
        if details is not None
    ]
    factor_deltas.sort(key=lambda item: abs(item[1]), reverse=True)

    advantages = [item[2] for item in factor_deltas if item[1] > 0][:3]
    tradeoffs = [item[2] for item in factor_deltas if item[1] < 0][:2]

    if winner.get("source_count", 0) <= 0:
        tradeoffs.append(f"{winner['panel_id']} still lacks source backing.")
    if winner.get("completed_workflow_count", 0) <= 0 and other.get(
        "completed_workflow_count", 0
    ) > 0:
        tradeoffs.append(
            f"{winner['panel_id']} has a weaker execution trace than {other['panel_id']}."
        )
    if (
        not tradeoffs
        and float(winner.get("score", 0.0)) - float(other.get("score", 0.0)) < 1.0
    ):
        tradeoffs.append(
            "The score gap is narrow, so the recommendation is directionally strong but not absolute."
        )

    return {
        "against_panel_id": other["panel_id"],
        "against_model_id": other["model_id"],
        "score_gap": round(
            float(winner.get("score", 0.0)) - float(other.get("score", 0.0)),
            2,
        ),
        "recommended_advantages": advantages,
        "tradeoffs": tradeoffs,
        "factor_deltas": [
            {"factor": label, "delta": delta, "detail": detail}
            for label, delta, detail in factor_deltas[:4]
        ],
    }


def _build_consensus_points(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(candidates) < 2:
        return []

    term_panels: dict[str, list[str]] = {}
    for candidate in candidates:
        panel_id = str(candidate.get("panel_id") or "").strip()
        if not panel_id:
            continue
        for term in _extract_review_terms(candidate.get("content")):
            panels = term_panels.setdefault(term, [])
            if panel_id not in panels:
                panels.append(panel_id)

    threshold = max(2, (len(candidates) * 3 + 4) // 5)
    consensus = [
        {
            "term": term,
            "support_count": len(panel_ids),
            "panel_ids": panel_ids,
        }
        for term, panel_ids in term_panels.items()
        if len(panel_ids) >= threshold
    ]
    consensus.sort(key=lambda item: (-item["support_count"], item["term"]))
    return consensus[:8]


def _build_difference_points(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(candidates) < 2:
        return []

    candidate_terms = {
        str(candidate.get("panel_id") or "").strip(): _extract_review_terms(
            candidate.get("content")
        )
        for candidate in candidates
    }
    term_panel_counts: dict[str, int] = {}
    for terms in candidate_terms.values():
        for term in set(terms):
            term_panel_counts[term] = term_panel_counts.get(term, 0) + 1

    differences: list[dict[str, Any]] = []
    for candidate in candidates:
        panel_id = str(candidate.get("panel_id") or "").strip()
        if not panel_id:
            continue
        unique_terms = [
            term
            for term in candidate_terms.get(panel_id, [])
            if term_panel_counts.get(term, 0) == 1
        ][:5]
        concerns = [str(item) for item in candidate.get("concerns", []) if str(item).strip()]
        if not unique_terms and not concerns:
            continue
        note_parts: list[str] = []
        if unique_terms:
            note_parts.append(f"{panel_id} focuses on {', '.join(unique_terms[:3])}.")
        if concerns:
            note_parts.append(concerns[0])
        differences.append(
            {
                "panel_id": panel_id,
                "model_id": str(candidate.get("model_id") or ""),
                "unique_terms": unique_terms,
                "note": " ".join(note_parts).strip(),
            }
        )
    return differences[:8]


def _build_model_performance_items(
    candidates: list[dict[str, Any]],
    *,
    user_timestamp: float,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        timestamp = float(candidate.get("timestamp") or 0)
        latency_seconds: float | None = None
        chars_per_second: float | None = None
        if user_timestamp > 0 and timestamp >= user_timestamp:
            latency_seconds = round(timestamp - user_timestamp, 3)
            if latency_seconds > 0:
                chars_per_second = round(
                    float(candidate.get("content_length") or 0) / latency_seconds,
                    2,
                )

        items.append(
            {
                "panel_id": str(candidate.get("panel_id") or ""),
                "model_id": str(candidate.get("model_id") or ""),
                "latency_seconds": latency_seconds,
                "chars_per_second": chars_per_second,
                "content_length": int(candidate.get("content_length") or 0),
                "source_count": int(candidate.get("source_count") or 0),
                "completed_workflow_count": int(
                    candidate.get("completed_workflow_count") or 0
                ),
                "token_usage": dict(candidate.get("token_usage") or {}),
                "score": float(candidate.get("score") or 0.0),
            }
        )
    return items


def _build_token_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    estimated_count = 0
    for candidate in candidates:
        usage = dict(candidate.get("token_usage") or {})
        item = {
            "panel_id": str(candidate.get("panel_id") or ""),
            "model_id": str(candidate.get("model_id") or ""),
            "prompt_tokens": _safe_non_negative_int(usage.get("prompt_tokens")),
            "completion_tokens": _safe_non_negative_int(
                usage.get("completion_tokens")
            ),
            "total_tokens": _safe_non_negative_int(usage.get("total_tokens")),
            "estimated": bool(usage.get("estimated")),
            "estimation_method": str(usage.get("estimation_method") or ""),
        }
        for key in totals:
            totals[key] += item[key]
        if item["estimated"]:
            estimated_count += 1
        items.append(item)

    return {
        **totals,
        "estimated": estimated_count > 0,
        "estimated_count": estimated_count,
        "real_count": max(0, len(items) - estimated_count),
        "by_panel": items,
    }


def _build_synthesized_answer(
    recommended: dict[str, Any],
    consensus_points: list[dict[str, Any]],
    difference_points: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    recommended_excerpt = _clip_text(recommended.get("content"), 700)
    consensus_terms = [
        str(item.get("term") or "").strip()
        for item in consensus_points
        if str(item.get("term") or "").strip()
    ][:5]
    difference_notes = [
        str(item.get("note") or "").strip()
        for item in difference_points
        if str(item.get("note") or "").strip()
    ][:3]
    tradeoffs: list[str] = []
    for comparison in comparisons:
        for tradeoff in comparison.get("tradeoffs", []):
            normalized = str(tradeoff or "").strip()
            if normalized and normalized not in tradeoffs:
                tradeoffs.append(normalized)
            if len(tradeoffs) >= 3:
                break
        if len(tradeoffs) >= 3:
            break

    sections: list[str] = []
    if recommended_excerpt:
        sections.append(f"Best candidate base: {recommended_excerpt}")
    if consensus_terms:
        sections.append(f"Shared consensus: {', '.join(consensus_terms)}.")
    if tradeoffs:
        sections.append(f"Important tradeoffs: {' '.join(tradeoffs)}")
    if difference_notes:
        sections.append(f"Additional model-specific signals: {' '.join(difference_notes)}")

    answer = "\n\n".join(sections).strip()
    if not answer:
        answer = "No substantive answer content was available to synthesize."

    return {
        "answer": answer,
        "source_panel_id": str(recommended.get("panel_id") or ""),
        "source_model_id": str(recommended.get("model_id") or ""),
        "strategy": "deterministic_consensus_best_candidate",
        "consensus_terms": consensus_terms,
        "difference_notes": difference_notes,
        "tradeoffs": tradeoffs,
        "estimated": False,
    }


def _build_review_confidence(
    recommended: dict[str, Any],
    runner_up: dict[str, Any] | None,
    candidate_count: int,
) -> tuple[float, str]:
    confidence = 0.48
    if candidate_count <= 1:
        confidence += 0.12

    if recommended.get("source_count", 0) > 0:
        confidence += min(0.16, float(recommended["source_count"]) * 0.04)
    if recommended.get("completed_workflow_count", 0) > 0:
        confidence += min(0.12, float(recommended["completed_workflow_count"]) * 0.04)
    if recommended.get("content_length", 0) >= 120:
        confidence += 0.08
    elif recommended.get("content_length", 0) < 40:
        confidence -= 0.12

    score_gap = float(recommended.get("score", 0.0))
    if runner_up is not None:
        score_gap -= float(runner_up.get("score", 0.0))
    confidence += min(0.18, max(0.0, score_gap) * 0.06)

    if runner_up is not None and score_gap < 0.75:
        confidence -= 0.08
    if (
        recommended.get("source_count", 0) <= 0
        and recommended.get("completed_workflow_count", 0) <= 0
    ):
        confidence -= 0.08

    confidence = round(min(0.98, max(0.2, confidence)), 2)
    if confidence >= 0.8:
        label = "high"
    elif confidence >= 0.6:
        label = "medium"
    else:
        label = "low"
    return confidence, label


def _build_decision_factors(
    recommended: dict[str, Any],
    comparisons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    factors: list[dict[str, Any]] = []

    if recommended.get("source_count", 0) > 0:
        factors.append(
            {
                "factor": "evidence support",
                "winner_panel_id": recommended["panel_id"],
                "detail": f"{recommended['panel_id']} cites {recommended['source_count']} supporting sources.",
            }
        )
    if recommended.get("completed_workflow_count", 0) > 0:
        factors.append(
            {
                "factor": "workflow trace",
                "winner_panel_id": recommended["panel_id"],
                "detail": (
                    f"{recommended['panel_id']} keeps {recommended['completed_workflow_count']} completed workflow steps visible."
                ),
            }
        )
    if recommended.get("content_length", 0) >= 120:
        factors.append(
            {
                "factor": "answer depth",
                "winner_panel_id": recommended["panel_id"],
                "detail": f"{recommended['panel_id']} provides a more complete response body.",
            }
        )

    for comparison in comparisons:
        for delta in comparison.get("factor_deltas", []):
            factor = str(delta.get("factor") or "").strip()
            if not factor:
                continue
            if any(existing["factor"] == factor for existing in factors):
                continue
            if float(delta.get("delta", 0.0)) <= 0:
                continue
            factors.append(
                {
                    "factor": factor,
                    "winner_panel_id": recommended["panel_id"],
                    "detail": str(delta.get("detail") or "").strip(),
                }
            )
            if len(factors) >= 4:
                return factors

    return factors[:4]


def _build_review_summary(
    recommended: dict[str, Any],
    comparisons: list[dict[str, Any]],
) -> str:
    summary_parts = [f"Recommend {recommended['panel_id']}"]
    if recommended["source_count"] > 0:
        summary_parts.append("stronger evidence support")
    if recommended["completed_workflow_count"] > 0:
        summary_parts.append("clearer execution trace")
    elif recommended["content_length"] >= 120:
        summary_parts.append("more complete answer coverage")

    if comparisons:
        top_gap = float(comparisons[0].get("score_gap", 0.0))
        if top_gap >= 2.0:
            summary_parts.append("clear lead over alternatives")
        elif top_gap > 0:
            summary_parts.append("modest lead over alternatives")

    return ", ".join(summary_parts)


def _apply_answer_group_reviewer(
    base_payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    reviewer = _answer_group_reviewer
    if reviewer is None:
        return base_payload

    override = reviewer({**context, "default_review": base_payload})
    if not isinstance(override, dict):
        return base_payload

    merged = dict(base_payload)
    merged.update(override)
    merged["session_id"] = base_payload["session_id"]
    merged["answer_group_id"] = base_payload["answer_group_id"]
    merged.setdefault("review_mode", base_payload["review_mode"])
    merged.setdefault("reviewer_label", base_payload["reviewer_label"])
    merged.setdefault("responses", base_payload["responses"])
    merged.setdefault("comparisons", base_payload["comparisons"])
    merged.setdefault("consensus_points", base_payload["consensus_points"])
    merged.setdefault("difference_points", base_payload["difference_points"])
    merged.setdefault("model_performance", base_payload["model_performance"])
    merged.setdefault("token_usage", base_payload["token_usage"])
    merged.setdefault("token_summary", base_payload["token_summary"])
    merged.setdefault("synthesis", base_payload["synthesis"])
    merged.setdefault("synthesized_answer", base_payload["synthesized_answer"])
    merged.setdefault("preference_signal", base_payload["preference_signal"])
    merged.setdefault("decision_factors", base_payload["decision_factors"])
    merged.setdefault("why_recommended", base_payload["why_recommended"])
    return merged


def build_answer_preference_signal(
    review_payload: dict[str, Any],
    *,
    selected_panel_id: str,
    persisted: bool,
) -> dict[str, Any]:
    selected_panel_id = str(selected_panel_id or "").strip()
    responses = [
        item
        for item in review_payload.get("responses", [])
        if isinstance(item, dict)
    ]
    selected = next(
        (
            item
            for item in responses
            if str(item.get("panel_id") or "").strip() == selected_panel_id
        ),
        {},
    )
    alternatives = [
        str(item.get("panel_id") or "").strip()
        for item in responses
        if str(item.get("panel_id") or "").strip()
        and str(item.get("panel_id") or "").strip() != selected_panel_id
    ]
    return {
        "kind": "answer_winner_selected",
        "session_id": str(review_payload.get("session_id") or ""),
        "answer_group_id": str(review_payload.get("answer_group_id") or ""),
        "selected_panel_id": selected_panel_id,
        "selected_model_id": str(selected.get("model_id") or ""),
        "recommended_panel_id": str(review_payload.get("recommended_panel_id") or ""),
        "recommended_model_id": str(review_payload.get("recommended_model_id") or ""),
        "accepted_recommendation": selected_panel_id
        == str(review_payload.get("recommended_panel_id") or "").strip(),
        "alternative_panel_ids": alternatives,
        "confidence": float(review_payload.get("confidence") or 0.0),
        "persisted": bool(persisted),
        "persistence": {
            "store": "messages.feedback_value",
            "value": 1 if persisted else 0,
        },
    }


def _sqlite_history_db_path(history: Any) -> str | None:
    from backend.core.storage_runtime import DATABASE_PROVIDER_POSTGRES, database_provider

    # SQLite-only helpers accept filesystem paths; PostgreSQL histories expose a
    # db_path-compatible attribute containing the DSN, which must not be passed
    # back into SQLite connection helpers.
    if database_provider() == DATABASE_PROVIDER_POSTGRES:
        return None
    db_path = str(getattr(history, "db_path", "") or "").strip()
    return db_path or None


def record_answer_preference_signal(
    session_id: str,
    answer_group_id: str,
    selected_panel_id: str,
    review_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from backend.chat_store import set_message_feedback
    from backend.stores.factory import create_chat_message_history

    review = review_payload or build_answer_group_review_payload(session_id, answer_group_id)
    history = create_chat_message_history(session_id=session_id)
    history_db_path = _sqlite_history_db_path(history)
    persisted = (
        (
            set_message_feedback(
                session_id,
                feedback_value=1,
                panel_id=selected_panel_id,
                answer_group_id=answer_group_id,
                db_path=history_db_path,
            )
            if history_db_path
            else set_message_feedback(
                session_id,
                feedback_value=1,
                panel_id=selected_panel_id,
                answer_group_id=answer_group_id,
            )
        )
        is not None
    )
    return build_answer_preference_signal(
        review,
        selected_panel_id=selected_panel_id,
        persisted=persisted,
    )


def build_answer_group_review_payload(session_id: str, answer_group_id: str) -> dict[str, Any]:
    from backend.chat_store import get_session_panels
    from backend.stores.factory import create_chat_message_history

    history = create_chat_message_history(session_id=session_id)
    history_db_path = _sqlite_history_db_path(history)
    panels = (
        get_session_panels(session_id, db_path=history_db_path)
        if history_db_path
        else get_session_panels(session_id)
    )
    primary_panel_id = next(
        (
            str(panel.get("panel_id") or "").strip()
            for panel in panels
            if bool(panel.get("is_primary"))
        ),
        "",
    )

    latest_by_panel: dict[str, dict[str, Any]] = {}
    normalized_answer_group_id = str(answer_group_id or "").strip()
    user_timestamps: list[float] = []
    user_prompts: list[str] = []
    for panel in panels:
        panel_id = str(panel.get("panel_id") or "").strip()
        if not panel_id:
            continue
        for record in history.get_all_message_records(panel_id=panel_id):
            if (
                str(record.get("type") or "").strip().lower() == "human"
                and str(record.get("answer_group_id") or "").strip()
                == normalized_answer_group_id
            ):
                user_timestamps.append(float(record.get("timestamp") or 0))
                prompt = str(record.get("content") or "").strip()
                if prompt and prompt not in user_prompts:
                    user_prompts.append(prompt)
                continue
            if str(record.get("type") or "").strip().lower() != "ai":
                continue
            if str(record.get("panel_id") or "").strip() != panel_id:
                continue
            if str(record.get("answer_group_id") or "").strip() != normalized_answer_group_id:
                continue
            latest_by_panel[panel_id] = record

    if not latest_by_panel:
        for record in history.get_all_message_records(panel_id=""):
            if (
                str(record.get("type") or "").strip().lower() == "human"
                and str(record.get("answer_group_id") or "").strip()
                == normalized_answer_group_id
            ):
                user_timestamps.append(float(record.get("timestamp") or 0))
                prompt = str(record.get("content") or "").strip()
                if prompt and prompt not in user_prompts:
                    user_prompts.append(prompt)
                continue
            if str(record.get("type") or "").strip().lower() != "ai":
                continue
            panel_id = str(record.get("panel_id") or "").strip()
            if not panel_id:
                continue
            if str(record.get("answer_group_id") or "").strip() != normalized_answer_group_id:
                continue
            latest_by_panel[panel_id] = record

    if not user_prompts:
        for record in history.get_all_message_records(panel_id=""):
            if (
                str(record.get("type") or "").strip().lower() == "human"
                and str(record.get("answer_group_id") or "").strip()
                == normalized_answer_group_id
            ):
                user_timestamps.append(float(record.get("timestamp") or 0))
                prompt = str(record.get("content") or "").strip()
                if prompt and prompt not in user_prompts:
                    user_prompts.append(prompt)

    if not latest_by_panel:
        raise KeyError(answer_group_id)

    scored_candidates = [
        _score_answer_candidate(
            candidate,
            is_primary=(panel_id == primary_panel_id),
            prompt_text="\n\n".join(user_prompts),
        )
        for panel_id, candidate in latest_by_panel.items()
    ]
    scored_candidates.sort(
        key=lambda item: (
            item["score"],
            item["source_count"],
            item["completed_workflow_count"],
            item["content_length"],
            1 if item["is_primary_panel"] else 0,
            item["panel_id"],
        ),
        reverse=True,
    )

    recommended = scored_candidates[0]
    runner_up = scored_candidates[1] if len(scored_candidates) > 1 else None
    comparisons = [
        _build_candidate_comparison(recommended, candidate)
        for candidate in scored_candidates[1:]
    ]
    consensus_points = _build_consensus_points(scored_candidates)
    difference_points = _build_difference_points(scored_candidates)
    token_summary = _build_token_summary(scored_candidates)
    model_performance = _build_model_performance_items(
        scored_candidates,
        user_timestamp=min(user_timestamps) if user_timestamps else 0.0,
    )
    confidence, confidence_label = _build_review_confidence(
        recommended,
        runner_up,
        len(scored_candidates),
    )
    why_recommended = _build_review_summary(recommended, comparisons)
    decision_factors = _build_decision_factors(recommended, comparisons)
    synthesis = _build_synthesized_answer(
        recommended,
        consensus_points,
        difference_points,
        comparisons,
    )
    preference_signal = build_answer_preference_signal(
        {
            "session_id": session_id,
            "answer_group_id": str(answer_group_id or "").strip(),
            "recommended_panel_id": recommended["panel_id"],
            "recommended_model_id": recommended["model_id"],
            "confidence": confidence,
            "responses": scored_candidates,
        },
        selected_panel_id=recommended["panel_id"],
        persisted=False,
    )

    base_payload = {
        "session_id": session_id,
        "answer_group_id": str(answer_group_id or "").strip(),
        "review_mode": "heuristic",
        "reviewer_label": "heuristic-score-v1",
        "recommended_panel_id": recommended["panel_id"],
        "recommended_model_id": recommended["model_id"],
        "confidence": confidence,
        "confidence_label": confidence_label,
        "summary": why_recommended,
        "why_recommended": why_recommended,
        "decision_factors": decision_factors,
        "comparisons": comparisons,
        "consensus_points": consensus_points,
        "difference_points": difference_points,
        "token_usage": token_summary["by_panel"],
        "token_summary": token_summary,
        "synthesis": synthesis,
        "synthesized_answer": synthesis["answer"],
        "preference_signal": preference_signal,
        "model_performance": model_performance,
        "responses": scored_candidates,
    }
    return _apply_answer_group_reviewer(
        base_payload,
        {
            "session_id": session_id,
            "answer_group_id": str(answer_group_id or "").strip(),
            "primary_panel_id": primary_panel_id,
            "recommended": recommended,
            "runner_up": runner_up,
            "candidates": scored_candidates,
            "comparisons": comparisons,
        },
    )


def build_session_messages_payload(session_id: str) -> dict[str, Any]:
    from backend.chat_store import (
        CONTEXT_HISTORY_MESSAGES,
        get_session,
        get_session_panels,
    )
    from backend.stores.factory import create_chat_message_history

    history = create_chat_message_history(session_id=session_id)
    history_db_path = _sqlite_history_db_path(history)
    session = (
        get_session(session_id, db_path=history_db_path)
        if history_db_path
        else get_session(session_id)
    ) or {
        "session_id": session_id,
        "title": "",
        "updated_at": 0,
    }
    all_records = history.get_all_message_records()
    messages = [message_payload(record) for record in all_records]

    panels = (
        get_session_panels(session_id, db_path=history_db_path)
        if history_db_path
        else get_session_panels(session_id)
    )
    panel_messages: dict[str, list[dict[str, Any]]] = {}
    for panel in panels:
        panel_id = str(panel.get("panel_id") or "").strip()
        if not panel_id:
            continue
        panel_messages[panel_id] = [
            message_payload(record)
            for record in history.get_all_message_records(panel_id=panel_id)
        ]

    return {
        "session": session,
        "messages": messages,
        "context_limit": CONTEXT_HISTORY_MESSAGES,
        "total_messages": len(messages),
        "panels": panels,
        "panel_messages": panel_messages,
    }


def render_shared_session_html(payload: dict[str, Any], share_url: str) -> str:
    session = dict(payload.get("session") or {})
    messages = list(payload.get("messages") or [])
    title = str(session.get("title") or "鍏变韩浼氳瘽").strip() or "鍏变韩浼氳瘽"
    updated_at = float(session.get("updated_at") or 0)
    updated_label = (
        time.strftime("%Y-%m-%d %H:%M", time.localtime(updated_at))
        if updated_at > 0
        else "鏈煡"
    )

    message_cards: list[str] = []
    for message in messages:
        role = "鐢ㄦ埛" if message.get("role") == "user" else "鍔╂墜"
        role_class = "user" if message.get("role") == "user" else "assistant"
        content = escape(str(message.get("content") or "")).replace("\n", "<br>")

        image_html = ""
        images = [item for item in message.get("images", []) if isinstance(item, dict)]
        if images:
            image_html = "".join(
                f'<img src="{escape(str(image.get("data_url") or ""))}" '
                f'alt="{escape(str(image.get("name") or "鍥剧墖"))}" loading="lazy" />'
                for image in images
                if str(image.get("data_url") or "").strip()
            )
            if image_html:
                image_html = f'<div class="image-grid">{image_html}</div>'

        file_html = ""
        files = [item for item in message.get("files", []) if isinstance(item, dict)]
        if files:
            file_html = "".join(
                "<li>"
                f"<strong>{escape(str(file.get('name') or '闄勪欢'))}</strong>"
                f"<span>{escape(_clip_text(file.get('extracted_text') or '', 180))}</span>"
                "</li>"
                for file in files
            )
            file_html = f'<ul class="attachment-list">{file_html}</ul>'

        source_html = ""
        sources = [item for item in message.get("sources", []) if isinstance(item, dict)]
        if sources:
            source_html = "".join(
                "<li>"
                f"<strong>{escape(str(source.get('title') or '鏉ユ簮'))}</strong>"
                f"<span>{escape(_clip_text(source.get('snippet') or '', 180))}</span>"
                "</li>"
                for source in sources
            )
            source_html = f'<ul class="source-list">{source_html}</ul>'

        message_cards.append(
            f"""
            <article class="message-card {role_class}">
              <div class="message-head">
                <span class="role">{role}</span>
                <span class="meta">{escape(str(message.get('model_id') or ''))}</span>
              </div>
              <div class="message-body">{content or '<span class="muted">锛堢┖鍐呭锛?/span>'}</div>
              {image_html}
              {file_html}
              {source_html}
            </article>
            """
        )

    timeline = "\n".join(message_cards) or '<p class="empty">鏆傛棤娑堟伅鍐呭銆?/p>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7fb;
      --card: #ffffff;
      --text: #162032;
      --muted: #627089;
      --border: #d8e0ee;
      --accent: #2563eb;
      --accent-soft: rgba(37, 99, 235, 0.1);
      --assistant: #0f766e;
      --assistant-soft: rgba(15, 118, 110, 0.09);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: radial-gradient(circle at top, #ffffff 0%, var(--bg) 55%); color: var(--text); }}
    .page {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 56px; }}
    .hero {{ margin-bottom: 24px; padding: 28px; border: 1px solid var(--border); border-radius: 24px; background: rgba(255,255,255,0.92); box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08); }}
    .eyebrow {{ display: inline-flex; padding: 6px 10px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }}
    h1 {{ margin: 14px 0 8px; font-size: clamp(28px, 4vw, 42px); }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 14px; }}
    .summary span {{ padding: 8px 12px; border-radius: 999px; border: 1px solid var(--border); background: #fff; }}
    .share-url {{ margin-top: 14px; color: var(--muted); font-size: 13px; word-break: break-all; }}
    .timeline {{ display: grid; gap: 14px; }}
    .message-card {{ border: 1px solid var(--border); border-radius: 20px; padding: 18px; background: var(--card); box-shadow: 0 10px 26px rgba(15, 23, 42, 0.05); }}
    .message-card.user {{ border-left: 4px solid var(--accent); }}
    .message-card.assistant {{ border-left: 4px solid var(--assistant); }}
    .message-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 10px; }}
    .role {{ font-weight: 700; }}
    .meta, .muted, .empty {{ color: var(--muted); }}
    .message-body {{ line-height: 1.7; white-space: normal; }}
    .image-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 14px; }}
    .image-grid img {{ width: 100%; border-radius: 16px; border: 1px solid var(--border); background: #eef2ff; }}
    .attachment-list, .source-list {{ margin: 14px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }}
    .attachment-list li, .source-list li {{ padding: 12px; border-radius: 14px; background: #f8fafc; border: 1px solid var(--border); }}
    .attachment-list span, .source-list span {{ display: block; margin-top: 4px; color: var(--muted); line-height: 1.5; }}
    @media (max-width: 640px) {{
      .page {{ padding: 18px 14px 32px; }}
      .hero {{ padding: 20px; border-radius: 18px; }}
      .message-card {{ padding: 14px; border-radius: 16px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">鍏变韩浼氳瘽</div>
      <h1>{escape(title)}</h1>
      <div class="summary">
        <span>{len(messages)} messages</span>
        <span>Updated at {escape(updated_label)}</span>
        <span>Read-only access</span>
      </div>
      <div class="share-url">Share URL: {escape(share_url)}</div>
    </section>
    <section class="timeline">{timeline}</section>
  </main>
</body>
</html>"""


def render_shared_deck_html(deck: Any, share_url: str) -> str:
    slides = list(getattr(deck, "slides", []) or [])
    slide_html: list[str] = []
    for index, slide in enumerate(slides, start=1):
        blocks = []
        for block in list(getattr(slide, "blocks", []) or []):
            kind = getattr(block, "kind", "")
            content = getattr(block, "content", {}) or {}
            if kind == "bullet_list":
                items = "".join(
                    f"<li>{escape(str(item))}</li>"
                    for item in list(content.get("items") or [])
                    if str(item).strip()
                )
                if items:
                    blocks.append(f"<ul>{items}</ul>")
            else:
                text = str(content.get("text") or "").strip()
                if text:
                    blocks.append(f"<p>{escape(text)}</p>")

        notes = escape(str(getattr(slide, "speaker_notes", "") or "")).replace("\n", "<br>")
        slide_html.append(
            f"""
            <article class="slide-card">
              <div class="slide-meta">
                <span>Slide {index}</span>
                <span>{escape(_shared_slide_type_label(getattr(slide, 'type', 'content')))}</span>
                <span>{escape(_shared_quality_label(getattr(slide, 'quality_state', 'draft')))}</span>
              </div>
              <h2>{escape(str(getattr(slide, 'title', '') or 'Untitled slide'))}</h2>
              <p class="subtitle">{escape(str(getattr(slide, 'subtitle', '') or ''))}</p>
              <div class="slide-body">{''.join(blocks) or '<p class="empty">No content</p>'}</div>
              {f'<div class="notes"><strong>演讲备注</strong><div>{notes}</div></div>' if notes else ''}
            </article>
            """
        )

    title = escape(str(getattr(deck.meta, "title", "Shared deck")))
    raw_theme = str(getattr(deck.meta, "theme", "default") or "default").strip() or "default"
    theme = escape(_shared_theme_label(raw_theme))
    theme_attr = escape(raw_theme)
    source_mode = escape(
        _shared_source_mode_label(getattr(deck.meta, "source_mode", "chat_only"))
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #fffaf2;
      --card: rgba(255,255,255,0.94);
      --text: #3a2410;
      --muted: #7c5c3e;
      --border: #efd7be;
      --accent: #dd6b20;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; color: var(--text); background: radial-gradient(circle at top, #fff4e6 0%, var(--bg) 55%); }}
    .page {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 56px; }}
    .hero {{ padding: 28px; border-radius: 28px; border: 1px solid var(--border); background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(255,244,230,0.88)); box-shadow: 0 18px 50px rgba(120, 53, 15, 0.12); }}
    .eyebrow {{ display: inline-flex; padding: 6px 10px; border-radius: 999px; background: rgba(221,107,32,0.12); color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }}
    h1 {{ margin: 14px 0 8px; font-size: clamp(28px, 4vw, 42px); }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 14px; }}
    .summary span {{ padding: 8px 12px; border-radius: 999px; border: 1px solid var(--border); background: #fff; }}
    .share-url {{ margin-top: 14px; color: var(--muted); font-size: 13px; word-break: break-all; }}
    .grid {{ display: grid; gap: 16px; margin-top: 22px; }}
    .slide-card {{ padding: 22px; border-radius: 24px; border: 1px solid var(--border); background: var(--card); box-shadow: 0 14px 35px rgba(120, 53, 15, 0.08); }}
    .slide-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
    h2 {{ margin: 0 0 6px; font-size: 24px; }}
    .subtitle {{ margin: 0 0 16px; color: var(--muted); }}
    .slide-body p, .slide-body li {{ line-height: 1.7; }}
    .notes {{ margin-top: 18px; padding-top: 14px; border-top: 1px dashed var(--border); color: var(--muted); }}
    .empty {{ color: var(--muted); }}
    @media (max-width: 640px) {{
      .page {{ padding: 18px 14px 32px; }}
      .hero, .slide-card {{ padding: 18px; border-radius: 18px; }}
    }}
  </style>
</head>
<body data-deck-theme="{theme_attr}">
  <main class="page" data-deck-theme="{theme_attr}">
    <section class="hero">
      <div class="eyebrow">Shared deck</div>
      <h1>{title}</h1>
      <div class="summary">
        <span>{len(slides)} slides</span>
        <span>主题 {theme}</span>
        <span>来源 {source_mode}</span>
        <span>只读访问</span>
      </div>
      <div class="share-url" data-theme-name="{theme_attr}">Theme key: {theme_attr}</div>
      <div class="share-url">Share URL: {escape(share_url)}</div>
    </section>
    <section class="grid">{''.join(slide_html) or '<p class="empty">No slide content.</p>'}</section>
  </main>
</body>
</html>"""


def session_attachment_id(kind: str, attachment: dict[str, Any]) -> str:
    fingerprint = (
        str(attachment.get("data_url") or "").strip()
        or str(attachment.get("extracted_text") or "").strip()
        or "|".join(
            [
                str(attachment.get("name") or "").strip(),
                str(attachment.get("media_type") or "").strip(),
                str(int(attachment.get("size_bytes") or 0)),
            ]
        )
    )
    return "att_" + _content_hash(
        {
            "kind": kind,
            "name": str(attachment.get("name") or "").strip(),
            "media_type": str(attachment.get("media_type") or "").strip(),
            "fingerprint": fingerprint,
        }
    )[:20]


def collect_session_attachments(
    message_records: list[dict[str, Any]],
    *,
    preview_char_limit: int,
) -> dict[str, Any]:
    attachment_map: dict[str, dict[str, Any]] = {}
    attachment_turns: dict[str, set[str]] = {}

    for record in message_records:
        timestamp = float(record.get("timestamp") or 0)
        answer_group_id = str(record.get("answer_group_id") or "").strip()

        for kind, key in (("image", "images"), ("file", "files")):
            for raw_attachment in record.get(key, []):
                attachment = _base_model_payload(raw_attachment)
                attachment_id = session_attachment_id(kind, attachment)
                name = str(attachment.get("name") or "").strip()
                media_type = str(attachment.get("media_type") or "").strip()
                data_url = str(attachment.get("data_url") or "").strip()
                size_bytes = int(attachment.get("size_bytes") or 0)
                extracted_text = str(attachment.get("extracted_text") or "").strip()
                preview_text = (
                    _clip_attachment_preview_text(extracted_text, preview_char_limit)
                    if kind == "file" and extracted_text
                    else ""
                )

                existing = attachment_map.get(attachment_id)
                if not existing:
                    existing = {
                        "attachment_id": attachment_id,
                        "kind": kind,
                        "name": name,
                        "media_type": media_type,
                        "data_url": data_url,
                        "size_bytes": size_bytes,
                        "extracted_text": extracted_text,
                        "preview_text": preview_text,
                        "text_char_count": len(extracted_text),
                        "occurrence_count": 0,
                        "turn_count": 0,
                        "first_seen_at": timestamp,
                        "last_seen_at": timestamp,
                        "latest_answer_group_id": answer_group_id,
                    }
                    attachment_map[attachment_id] = existing

                existing["occurrence_count"] += 1
                existing["first_seen_at"] = min(
                    float(existing.get("first_seen_at") or timestamp),
                    timestamp,
                )
                if timestamp >= float(existing.get("last_seen_at") or 0):
                    existing["last_seen_at"] = timestamp
                    existing["latest_answer_group_id"] = answer_group_id

                if not existing.get("data_url") and data_url:
                    existing["data_url"] = data_url
                if kind == "file" and extracted_text and not existing.get("extracted_text"):
                    existing["extracted_text"] = extracted_text
                    existing["preview_text"] = preview_text
                    existing["text_char_count"] = len(extracted_text)

                if answer_group_id:
                    attachment_turns.setdefault(attachment_id, set()).add(answer_group_id)

    attachments = sorted(
        attachment_map.values(),
        key=lambda item: (
            -float(item.get("last_seen_at") or 0),
            str(item.get("name") or "").lower(),
        ),
    )

    for item in attachments:
        turns = attachment_turns.get(str(item.get("attachment_id") or ""), set())
        item["turn_count"] = len(turns) if turns else int(item.get("occurrence_count") or 0)

    summary = {
        "total_attachments": len(attachments),
        "file_count": sum(1 for item in attachments if item.get("kind") == "file"),
        "image_count": sum(1 for item in attachments if item.get("kind") == "image"),
        "text_ready_count": sum(1 for item in attachments if item.get("preview_text")),
        "reusable_count": sum(1 for item in attachments if item.get("data_url")),
        "total_size_bytes": sum(int(item.get("size_bytes") or 0) for item in attachments),
    }

    return {
        "attachments": attachments,
        "summary": summary,
    }


def find_session_attachment(
    session_id: str,
    attachment_id: str,
    *,
    preview_char_limit: int,
) -> dict[str, Any] | None:
    from backend.stores.factory import create_chat_message_history

    history = create_chat_message_history(session_id=session_id)
    payload = collect_session_attachments(
        history.get_all_message_records(),
        preview_char_limit=preview_char_limit,
    )
    for attachment in payload.get("attachments", []):
        if str(attachment.get("attachment_id") or "").strip() == attachment_id:
            return attachment
    return None
