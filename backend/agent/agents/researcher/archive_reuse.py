"""Research V2 archive reuse helpers."""

from __future__ import annotations

from typing import Any


def _compact_text(value: Any, max_length: int = 320) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= max_length:
        return text
    return f"{text[: max(0, max_length - 3)].rstrip()}..."


def _string_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, dict):
        for key in ("claim_id", "source_id", "id", "url"):
            text = str(value.get(key) or "").strip()
            if text:
                return [text]
        return []
    if not isinstance(value, list):
        return []

    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        for text in _string_items(item):
            if text and text not in seen:
                items.append(text)
                seen.add(text)
    return items


def _coerce_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _archive_content(archive: dict[str, Any]) -> dict[str, Any]:
    content = archive.get("content")
    return dict(content) if isinstance(content, dict) else {}


def _archive_report(archive: dict[str, Any]) -> dict[str, Any]:
    content = _archive_content(archive)
    report = archive.get("research_report") or content.get("research_report")
    return dict(report) if isinstance(report, dict) else {}


def _archive_chains(archive: dict[str, Any]) -> list[dict[str, Any]]:
    content = _archive_content(archive)
    report = _archive_report(archive)
    return (
        _coerce_items(archive.get("claim_evidence_chains"))
        or _coerce_items(content.get("claim_evidence_chains"))
        or _coerce_items(report.get("claim_evidence_chains"))
        or _coerce_items(archive.get("preview_claims"))
    )


def _archive_sources(archive: dict[str, Any]) -> list[dict[str, Any]]:
    content = _archive_content(archive)
    report = _archive_report(archive)
    return (
        _coerce_items(archive.get("sources"))
        or _coerce_items(archive.get("preview_sources"))
        or _coerce_items(content.get("sources"))
        or _coerce_items(report.get("sources"))
    )


def _source_id(source: dict[str, Any], index: int) -> str:
    return str(
        source.get("source_id")
        or source.get("doc_id")
        or source.get("id")
        or source.get("url")
        or f"source-{index + 1}"
    ).strip()


def _claim_id(chain: dict[str, Any], index: int) -> str:
    return str(chain.get("claim_id") or chain.get("id") or f"claim-{index + 1}").strip()


def _token_score(query: str, text: str) -> float:
    tokens = {
        token
        for token in query.lower().replace("/", " ").replace("-", " ").split()
        if len(token) >= 2
    }
    if not tokens:
        return 0.0
    haystack = text.lower()
    matched = sum(1 for token in tokens if token in haystack)
    return round(matched / len(tokens), 4)


def summarize_reusable_archives(
    archives: list[dict[str, Any]],
    *,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Create compact archive reuse candidates for Research V2 artifacts."""
    candidates: list[dict[str, Any]] = []
    for archive in archives:
        report = _archive_report(archive)
        chains = _archive_chains(archive)
        sources = _archive_sources(archive)
        archive_id = str(
            archive.get("artifact_id")
            or archive.get("archive_id")
            or archive.get("id")
            or ""
        ).strip()
        title = _compact_text(archive.get("title") or report.get("query") or "Research archive", 160)
        summary = _compact_text(report.get("summary") or archive.get("summary") or "", 360)
        searchable = " ".join(
            [
                title,
                summary,
                str(report.get("query") or ""),
                " ".join(str(item.get("claim_text") or item.get("text") or "") for item in chains),
                " ".join(str(item.get("title") or item.get("snippet") or "") for item in sources),
            ]
        )
        reuse_score = _token_score(query, searchable)
        if query.strip() and reuse_score <= 0:
            continue

        matched_claims = []
        for index, chain in enumerate(chains[:5]):
            matched_claims.append(
                {
                    "claim_id": _claim_id(chain, index),
                    "claim_text": _compact_text(
                        chain.get("claim_text") or chain.get("text") or chain.get("claim"),
                        220,
                    ),
                    "status": str(chain.get("status") or "").strip(),
                    "source_ids": _string_items(
                        chain.get("supporting_source_ids")
                        or chain.get("source_ids")
                        or chain.get("sources")
                    ),
                }
            )

        source_preview = []
        for index, source in enumerate(sources[:5]):
            source_preview.append(
                {
                    "source_id": _source_id(source, index),
                    "title": _compact_text(source.get("title") or source.get("url"), 180),
                    "url": str(source.get("url") or "").strip(),
                    "source_tier": str(source.get("source_tier") or "").strip(),
                    "provider": str(source.get("provider") or "").strip(),
                }
            )

        candidates.append(
            {
                "archive_id": archive_id,
                "artifact_id": archive_id,
                "title": title,
                "query": _compact_text(report.get("query") or archive.get("query") or "", 180),
                "summary": summary,
                "reuse_score": reuse_score,
                "claim_count": len(chains),
                "source_count": len(sources),
                "matched_claims": matched_claims,
                "source_preview": source_preview,
            }
        )

    return sorted(
        candidates,
        key=lambda item: (-float(item.get("reuse_score") or 0), str(item.get("title") or "")),
    )[: max(1, limit)]


def build_archive_reuse_context(
    context: dict[str, Any],
    *,
    query: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Read reusable archive candidates from runtime context."""
    raw_archives = (
        context.get("research_archive_candidates")
        or context.get("research_archives")
        or context.get("archives")
        or []
    )
    archives = _coerce_items(raw_archives)
    candidates = summarize_reusable_archives(archives, query=query, limit=limit)
    return {
        "enabled": bool(candidates),
        "query": query,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


__all__ = ["build_archive_reuse_context", "summarize_reusable_archives"]
