"""Research archive payload and filtering helpers."""

from __future__ import annotations

from typing import Any

def artifact_content(artifact: Any) -> dict[str, Any]:
    content = getattr(artifact, "content", {})
    return dict(content) if isinstance(content, dict) else {}

def research_report_content(artifact: Any) -> dict[str, Any]:
    content = artifact_content(artifact)
    report = content.get("research_report")
    if isinstance(report, dict):
        return dict(report)
    return {}

def is_research_archive_artifact(artifact: Any) -> bool:
    content = artifact_content(artifact)
    report = research_report_content(artifact)
    artifact_type = str(getattr(artifact, "artifact_type", "") or "").strip()
    if artifact_type == "research_archive":
        return True
    if bool(content.get("research_archive")):
        return True
    return (
        str(report.get("type") or "").strip() == "research_report"
        and str(report.get("version") or "").strip().lower() == "v2"
    )

def coerce_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]

def research_archive_sources(
    content: dict[str, Any],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    sources = coerce_items(report.get("sources"))
    if sources:
        return sources
    return coerce_items(content.get("sources"))

def research_archive_task_id(artifact: Any, content: dict[str, Any]) -> str:
    task_id = str(content.get("task_id") or "").strip()
    if task_id:
        return task_id
    linked_type = str(getattr(artifact, "linked_resource_type", "") or "").strip()
    if linked_type == "task":
        return str(getattr(artifact, "linked_resource_id", "") or "").strip()
    return ""

def compact_text(value: Any, max_length: int = 280) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= max_length:
        return text
    return f"{text[: max(0, max_length - 3)].rstrip()}..."

def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

def string_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, dict):
        for key in ("source_id", "claim_id", "id", "anchor_id"):
            text = str(value.get(key) or "").strip()
            if text:
                return [text]
        return []
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        for text in string_items(item):
            if text and text not in seen:
                items.append(text)
                seen.add(text)
    return items

def collect_id_fields(item: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for text in string_items(item.get(key)):
            if text and text not in seen:
                values.append(text)
                seen.add(text)
    return values

def source_identifier(source: dict[str, Any]) -> str:
    return str(source.get("source_id") or source.get("id") or source.get("url") or "").strip()

def claim_identifier(claim: dict[str, Any], index: int) -> str:
    claim_id = str(claim.get("claim_id") or claim.get("id") or "").strip()
    return claim_id or f"claim-{index + 1}"

def coerce_citation_sections(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        sections: list[dict[str, Any]] = []
        for key, raw_item in value.items():
            if isinstance(raw_item, dict):
                item = dict(raw_item)
                item.setdefault("anchor_id", key)
                item.setdefault("paragraph_id", key)
                sections.append(item)
            elif isinstance(raw_item, list):
                for nested in raw_item:
                    if isinstance(nested, dict):
                        item = dict(nested)
                        item.setdefault("anchor_id", key)
                        item.setdefault("paragraph_id", key)
                        sections.append(item)
            elif str(raw_item or "").strip():
                sections.append(
                    {
                        "anchor_id": key,
                        "paragraph_id": key,
                        "text": str(raw_item).strip(),
                    }
                )
        return sections
    return coerce_items(value)

def research_paragraph_citations(
    content: dict[str, Any],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_sections: list[dict[str, Any]] = []
    for container in (content, report):
        for key in ("paragraph_citations", "citation_map", "paragraphs", "sections"):
            raw_sections.extend(coerce_citation_sections(container.get(key)))

    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_sections):
        paragraph_id = str(
            item.get("paragraph_id")
            or item.get("paragraphId")
            or item.get("paragraph")
            or ""
        ).strip()
        section_id = str(
            item.get("section_id")
            or item.get("sectionId")
            or item.get("section")
            or ""
        ).strip()
        anchor_id = str(item.get("anchor_id") or item.get("anchorId") or item.get("id") or "").strip()
        text = compact_text(
            item.get("text")
            or item.get("content")
            or item.get("body")
            or item.get("summary")
            or item.get("title"),
            600,
        )
        claim_ids = collect_id_fields(
            item,
            ("claim_ids", "claimIds", "claims", "claim_id", "claimId"),
        )
        source_ids = collect_id_fields(
            item,
            (
                "source_ids",
                "sourceIds",
                "sources",
                "citations",
                "evidence_source_ids",
                "evidence",
                "source_id",
                "sourceId",
            ),
        )
        if not any((paragraph_id, section_id, anchor_id, text, claim_ids, source_ids)):
            continue
        if not paragraph_id and not section_id and not anchor_id:
            paragraph_id = f"paragraph-{index + 1}"
        dedupe_key = (paragraph_id or section_id, anchor_id, text)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        citations.append(
            {
                "paragraph_id": paragraph_id,
                "section_id": section_id,
                "text": text,
                "claim_ids": claim_ids,
                "source_ids": source_ids,
                "anchor_id": anchor_id or paragraph_id or section_id,
            }
        )
    return citations

def claim_source_ids(chain: dict[str, Any]) -> list[str]:
    return collect_id_fields(
        chain,
        (
            "source_ids",
            "sourceIds",
            "supporting_source_ids",
            "supportingSourceIds",
            "supporting_sources",
            "supportingSources",
            "sources",
            "evidence_sources",
            "evidenceSources",
            "evidence",
            "citations",
        ),
    )

def research_navigation_index(
    paragraph_citations: list[dict[str, Any]],
) -> dict[str, Any]:
    paragraph_to_claims: dict[str, list[str]] = {}
    paragraph_to_sources: dict[str, list[str]] = {}
    claim_to_paragraphs: dict[str, list[str]] = {}
    source_to_paragraphs: dict[str, list[str]] = {}
    links: list[dict[str, str]] = []
    seen_links: set[tuple[str, str, str]] = set()

    def add_unique(mapping: dict[str, list[str]], key: str, value: str) -> None:
        if not key or not value:
            return
        items = mapping.setdefault(key, [])
        if value not in items:
            items.append(value)

    for paragraph in paragraph_citations:
        paragraph_id = str(
            paragraph.get("paragraph_id")
            or paragraph.get("anchor_id")
            or paragraph.get("section_id")
            or ""
        ).strip()
        if not paragraph_id:
            continue
        anchor_id = str(paragraph.get("anchor_id") or paragraph_id).strip()
        for claim_id in string_items(paragraph.get("claim_ids")):
            add_unique(paragraph_to_claims, paragraph_id, claim_id)
            add_unique(claim_to_paragraphs, claim_id, paragraph_id)
            link_key = (paragraph_id, claim_id, "claim")
            if link_key not in seen_links:
                links.append(
                    {
                        "paragraph_id": paragraph_id,
                        "anchor_id": anchor_id,
                        "claim_id": claim_id,
                        "link_type": "claim",
                    }
                )
                seen_links.add(link_key)
        for source_id in string_items(paragraph.get("source_ids")):
            add_unique(paragraph_to_sources, paragraph_id, source_id)
            add_unique(source_to_paragraphs, source_id, paragraph_id)
            link_key = (paragraph_id, source_id, "source")
            if link_key not in seen_links:
                links.append(
                    {
                        "paragraph_id": paragraph_id,
                        "anchor_id": anchor_id,
                        "source_id": source_id,
                        "link_type": "source",
                    }
                )
                seen_links.add(link_key)

    return {
        "paragraph_to_claims": paragraph_to_claims,
        "paragraph_to_sources": paragraph_to_sources,
        "claim_to_paragraphs": claim_to_paragraphs,
        "source_to_paragraphs": source_to_paragraphs,
        "links": links,
    }

def research_citation_graph(
    chains: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    paragraph_citations: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    edge_ids: set[tuple[str, str, str]] = set()

    for paragraph in paragraph_citations or []:
        paragraph_id = str(
            paragraph.get("paragraph_id")
            or paragraph.get("anchor_id")
            or paragraph.get("section_id")
            or ""
        ).strip()
        if not paragraph_id:
            continue
        node_id = f"paragraph:{paragraph_id}"
        if node_id not in node_ids:
            nodes.append(
                {
                    "id": node_id,
                    "type": "paragraph",
                    "paragraph_id": paragraph_id,
                    "anchor_id": str(paragraph.get("anchor_id") or paragraph_id).strip(),
                    "text": compact_text(paragraph.get("text"), 240),
                }
            )
            node_ids.add(node_id)
        for claim_id in string_items(paragraph.get("claim_ids")):
            claim_node_id = f"claim:{claim_id}"
            if claim_node_id not in node_ids:
                nodes.append(
                    {
                        "id": claim_node_id,
                        "type": "claim",
                        "claim_id": claim_id,
                    }
                )
                node_ids.add(claim_node_id)
            edge_key = (node_id, claim_node_id, "mentions")
            if edge_key not in edge_ids:
                edges.append(
                    {
                        "source": node_id,
                        "target": claim_node_id,
                        "type": "mentions",
                    }
                )
                edge_ids.add(edge_key)
        for source_id in string_items(paragraph.get("source_ids")):
            source_node_id = f"source:{source_id}"
            if source_node_id not in node_ids:
                nodes.append(
                    {
                        "id": source_node_id,
                        "type": "source",
                        "source_id": source_id,
                    }
                )
                node_ids.add(source_node_id)
            edge_key = (node_id, source_node_id, "cites")
            if edge_key not in edge_ids:
                edges.append(
                    {
                        "source": node_id,
                        "target": source_node_id,
                        "type": "cites",
                    }
                )
                edge_ids.add(edge_key)

    for index, chain in enumerate(chains):
        claim_id = claim_identifier(chain, index)
        node_id = f"claim:{claim_id}"
        claim_text = compact_text(
            chain.get("claim_text")
            or chain.get("claim")
            or chain.get("text")
            or chain.get("statement"),
            360,
        )
        if node_id not in node_ids:
            nodes.append(
                {
                    "id": node_id,
                    "type": "claim",
                    "claim_id": claim_id,
                    "text": claim_text,
                }
            )
            node_ids.add(node_id)
        else:
            for node in nodes:
                if node.get("id") == node_id and claim_text:
                    node.setdefault("text", claim_text)
                    break
        for source_id in claim_source_ids(chain):
            source_node_id = f"source:{source_id}"
            if source_node_id not in node_ids:
                nodes.append(
                    {
                        "id": source_node_id,
                        "type": "source",
                        "source_id": source_id,
                    }
                )
                node_ids.add(source_node_id)
            edge_key = (node_id, source_node_id, "supports")
            if edge_key not in edge_ids:
                edges.append(
                    {
                        "source": source_node_id,
                        "target": node_id,
                        "type": "supports",
                    }
                )
                edge_ids.add(edge_key)

    for source in sources:
        source_id = source_identifier(source)
        if not source_id:
            continue
        node_id = f"source:{source_id}"
        if node_id in node_ids:
            for node in nodes:
                if node.get("id") == node_id:
                    node.update(
                        {
                            "title": compact_text(
                                source.get("title") or source.get("name") or source.get("url"),
                                180,
                            ),
                            "url": str(source.get("url") or source.get("href") or "").strip(),
                        }
                    )
                    break
            continue
        nodes.append(
            {
                "id": node_id,
                "type": "source",
                "source_id": source_id,
                "title": compact_text(source.get("title") or source.get("name") or source.get("url"), 180),
                "url": str(source.get("url") or source.get("href") or "").strip(),
            }
        )
        node_ids.add(node_id)
    return {"nodes": nodes, "edges": edges}

def research_conflict_review_records(content: dict[str, Any]) -> list[dict[str, Any]]:
    records = coerce_items(content.get("conflict_review_resolutions"))
    normalized: list[dict[str, Any]] = []
    for record in records:
        conflict_id = str(record.get("conflict_id") or "").strip()
        claim_id = str(record.get("claim_id") or "").strip()
        if not conflict_id and not claim_id:
            continue
        normalized.append(
            {
                "conflict_id": conflict_id or claim_id,
                "claim_id": claim_id,
                "status": str(record.get("status") or "reviewed").strip() or "reviewed",
                "resolution": compact_text(record.get("resolution"), 500),
                "note": compact_text(record.get("note"), 500),
                "reviewer": compact_text(record.get("reviewer"), 120),
                "updated_at": float(record.get("updated_at") or 0),
            }
        )
    return normalized

def research_conflict_summary(
    chains: list[dict[str, Any]],
    review_records: list[dict[str, Any]] | None = None,
    archive_conflict_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conflict_statuses = ("contradiction", "contradicted", "conflict", "conflicting", "needs_attention")
    items: list[dict[str, Any]] = []
    conflicting_claims: list[str] = []
    reviews_by_claim = {
        str(record.get("claim_id") or "").strip(): record
        for record in (review_records or [])
        if str(record.get("claim_id") or "").strip()
    }
    reviews_by_conflict = {
        str(record.get("conflict_id") or "").strip(): record
        for record in (review_records or [])
        if str(record.get("conflict_id") or "").strip()
    }
    for index, chain in enumerate(chains):
        status = str(chain.get("status") or "").strip().lower()
        conflict_text = compact_text(
            chain.get("conflict_text")
            or chain.get("contradiction_text")
            or chain.get("needs_attention_reason")
            or chain.get("attention_reason")
            or chain.get("conflict")
            or chain.get("contradiction"),
            500,
        )
        has_signal = any(token in status for token in conflict_statuses) or any(
            bool(chain.get(key))
            for key in (
                "conflict",
                "conflicting",
                "contradiction",
                "contradicted",
                "has_conflict",
                "needs_attention",
            )
        )
        if not has_signal and not conflict_text:
            continue
        claim_id = claim_identifier(chain, index)
        conflict_id = str(chain.get("conflict_id") or chain.get("id") or claim_id).strip()
        review = reviews_by_conflict.get(conflict_id) or reviews_by_claim.get(claim_id)
        claim_text = compact_text(
            chain.get("claim_text")
            or chain.get("claim")
            or chain.get("text")
            or chain.get("statement"),
            500,
        )
        conflicting_claims.append(claim_id)
        items.append(
            {
                "conflict_id": conflict_id,
                "claim_id": claim_id,
                "claim_text": claim_text,
                "status": status,
                "text": compact_text(
                    conflict_text
                    or claim_text,
                    500,
                ),
                "source_ids": claim_source_ids(chain),
                "review_status": str(review.get("status") or "unreviewed").strip()
                if review
                else "unreviewed",
                "review": review or None,
            }
        )
    archive_conflicts = archive_conflict_review.get("conflicts") if isinstance(archive_conflict_review, dict) else []
    if isinstance(archive_conflicts, list):
        for conflict in archive_conflicts:
            if not isinstance(conflict, dict):
                continue
            claim_id = str(conflict.get("claim_id") or "").strip()
            archive_id = str(conflict.get("archive_id") or "").strip()
            archive_claim_id = str(conflict.get("archive_claim_id") or "").strip()
            if not claim_id or not archive_id or not archive_claim_id:
                continue
            conflict_id = str(
                conflict.get("conflict_id")
                or f"archive:{archive_id}:{archive_claim_id}:{claim_id}"
            ).strip()
            review = reviews_by_conflict.get(conflict_id) or reviews_by_claim.get(claim_id)
            claim_text = compact_text(
                conflict.get("claim_text")
                or conflict.get("current_claim_text")
                or conflict.get("text"),
                500,
            )
            archive_claim_text = compact_text(conflict.get("archive_claim_text"), 500)
            text = compact_text(
                conflict.get("conflict_text")
                or " ".join(part for part in [claim_text, archive_claim_text] if part),
                500,
            )
            conflicting_claims.append(claim_id)
            source_ids_value = conflict.get("source_ids")
            raw_source_ids = (
                source_ids_value
                if isinstance(source_ids_value, list)
                else [conflict.get("source_id")]
            )
            items.append(
                {
                    "conflict_id": conflict_id,
                    "claim_id": claim_id,
                    "claim_text": claim_text,
                    "archive_id": archive_id,
                    "archive_claim_id": archive_claim_id,
                    "archive_claim_text": archive_claim_text,
                    "status": str(conflict.get("severity") or "needs_review").strip().lower(),
                    "text": text,
                    "source_ids": [
                        str(source_id).strip()
                        for source_id in raw_source_ids
                        if str(source_id or "").strip()
                    ],
                    "review_status": str(review.get("status") or "unreviewed").strip()
                    if review
                    else "unreviewed",
                    "review": review or None,
                }
            )
    return {
        "total": len(items),
        "conflicting_claims": conflicting_claims,
        "items": items,
        "reviewed": sum(1 for item in items if item.get("review_status") != "unreviewed"),
        "unreviewed": sum(1 for item in items if item.get("review_status") == "unreviewed"),
    }

def research_claim_preview(
    chains: list[dict[str, Any]],
    report: dict[str, Any],
    limit: int = 3,
) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for chain in chains:
        claim_text = (
            chain.get("claim_text")
            or chain.get("claim")
            or chain.get("text")
            or chain.get("statement")
        )
        if not str(claim_text or "").strip():
            continue
        previews.append(
            {
                "claim_id": str(chain.get("claim_id") or chain.get("id") or "").strip(),
                "claim_text": compact_text(claim_text),
                "status": str(chain.get("status") or "").strip(),
                "supporting_source_count": safe_int(chain.get("supporting_source_count")),
                "has_primary_source": bool(chain.get("has_primary_source")),
            }
        )
        if len(previews) >= limit:
            return previews

    for claim in coerce_items(report.get("atomic_claims")):
        claim_text = claim.get("claim_text") or claim.get("claim") or claim.get("text")
        if not str(claim_text or "").strip():
            continue
        previews.append(
            {
                "claim_id": str(claim.get("claim_id") or claim.get("id") or "").strip(),
                "claim_text": compact_text(claim_text),
                "status": str(claim.get("status") or "").strip(),
                "supporting_source_count": 0,
                "has_primary_source": False,
            }
        )
        if len(previews) >= limit:
            break
    return previews

def research_source_preview(
    sources: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for source in sources:
        title = source.get("title") or source.get("name") or source.get("url")
        url = source.get("url") or source.get("href")
        if not str(title or url or "").strip():
            continue
        previews.append(
            {
                "source_id": str(source.get("source_id") or source.get("id") or "").strip(),
                "title": compact_text(title, 180),
                "url": str(url or "").strip(),
                "source_tier": str(source.get("source_tier") or "").strip(),
                "freshness_band": str(source.get("freshness_band") or "").strip(),
                "snippet": compact_text(
                    source.get("snippet") or source.get("summary") or source.get("content"),
                    220,
                ),
            }
        )
        if len(previews) >= limit:
            break
    return previews

def source_capability_items(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [
            str(key).strip()
            for key, enabled in value.items()
            if str(key).strip() and enabled is not False and enabled is not None
        ]
    return string_items(value)

def research_provider_capability_coverage(
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    providers: list[str] = []
    for source in sources:
        source_id = source_identifier(source)
        provider = str(
            source.get("provider")
            or source.get("provider_name")
            or source.get("search_provider")
            or ""
        ).strip()
        capabilities = source_capability_items(
            source.get("capabilities")
            or source.get("capability_scopes")
            or source.get("declared_capabilities")
        )
        if not provider and not capabilities:
            continue
        if provider and provider not in providers:
            providers.append(provider)
        items.append(
            {
                "source_id": source_id,
                "provider": provider,
                "capabilities": capabilities,
                "declared": bool(provider and capabilities),
            }
        )
    return {
        "total_sources": len(sources),
        "declared_sources": sum(1 for item in items if item.get("declared")),
        "providers": providers,
        "items": items,
    }

def research_citation_panel_payload(
    chains: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    verification_summary: dict[str, Any],
) -> dict[str, Any]:
    source_index: dict[str, dict[str, Any]] = {}
    claim_source_links: list[dict[str, str]] = []
    seen_links: set[tuple[str, str]] = set()

    for index, source in enumerate(sources, start=1):
        source_id = source_identifier(source) or str(source.get("doc_id") or f"source-{index}").strip()
        if not source_id:
            continue
        source_index[source_id] = {
            "source_id": source_id,
            "source_index": index,
            "title": compact_text(source.get("title") or source.get("name") or source.get("url"), 180),
            "url": str(source.get("url") or source.get("href") or "").strip(),
            "domain": str(source.get("domain") or "").strip(),
            "provider": str(source.get("provider") or source.get("provider_name") or "").strip(),
            "source_tier": str(source.get("source_tier") or "").strip(),
            "source_family": str(source.get("source_family") or "").strip(),
            "freshness_band": str(source.get("freshness_band") or "").strip(),
            "published_at": str(source.get("published_at") or "").strip(),
            "snippet": compact_text(source.get("snippet") or source.get("summary") or source.get("content"), 500),
        }

    for index, chain in enumerate(chains):
        claim_id = claim_identifier(chain, index)
        for source_id in claim_source_ids(chain):
            if not claim_id or not source_id:
                continue
            link_key = (claim_id, source_id)
            if link_key in seen_links:
                continue
            claim_source_links.append(
                {
                    "claim_id": claim_id,
                    "source_id": source_id,
                    "link_type": "supports",
                }
            )
            seen_links.add(link_key)

    return {
        "version": "v2",
        "claim_evidence_chains": chains,
        "claim_verification_summary": verification_summary,
        "source_index": source_index,
        "claim_source_links": claim_source_links,
    }

def research_archive_search_text(
    artifact: Any,
    content: dict[str, Any],
    report: dict[str, Any],
    sources: list[dict[str, Any]],
    chains: list[dict[str, Any]],
) -> str:
    paragraph_citations = research_paragraph_citations(content, report)
    review_records = research_conflict_review_records(content)
    conflict_summary = research_conflict_summary(
        chains,
        review_records,
        archive_conflict_review=report.get("archive_conflict_review")
        if isinstance(report.get("archive_conflict_review"), dict)
        else None,
    )
    parts: list[str] = [
        getattr(artifact, "artifact_id", ""),
        getattr(artifact, "title", ""),
        getattr(artifact, "session_id", ""),
        content.get("markdown", ""),
        report.get("query", ""),
        report.get("summary", ""),
    ]
    for claim in chains:
        parts.extend(
            [
                claim.get("claim_id", ""),
                claim.get("claim_text", ""),
                claim.get("claim", ""),
                claim.get("text", ""),
                claim.get("conflict_text", ""),
                claim.get("contradiction_text", ""),
                claim.get("needs_attention_reason", ""),
                claim.get("attention_reason", ""),
                claim.get("conflict", ""),
                claim.get("contradiction", ""),
            ]
        )
    for source in sources:
        parts.extend(
            [
                source.get("source_id", ""),
                source.get("id", ""),
                source.get("title", ""),
                source.get("url", ""),
                source.get("snippet", ""),
                source.get("summary", ""),
            ]
        )
    for paragraph in paragraph_citations:
        parts.extend(
            [
                paragraph.get("paragraph_id", ""),
                paragraph.get("section_id", ""),
                paragraph.get("anchor_id", ""),
                paragraph.get("text", ""),
                " ".join(paragraph.get("claim_ids", [])),
                " ".join(paragraph.get("source_ids", [])),
            ]
        )
    for item in conflict_summary["items"]:
        parts.extend(
            [
                item.get("conflict_id", ""),
                item.get("claim_id", ""),
                item.get("status", ""),
                item.get("text", ""),
                item.get("review_status", ""),
                " ".join(item.get("source_ids", [])),
            ]
        )
    for review in review_records:
        parts.extend(
            [
                review.get("conflict_id", ""),
                review.get("claim_id", ""),
                review.get("status", ""),
                review.get("resolution", ""),
                review.get("note", ""),
                review.get("reviewer", ""),
            ]
        )
    return " ".join(str(part or "") for part in parts).lower()

def research_archive_payload(artifact: Any) -> dict[str, Any]:
    content = artifact_content(artifact)
    report = research_report_content(artifact)
    chains = coerce_items(content.get("claim_evidence_chains")) or coerce_items(
        report.get("claim_evidence_chains")
    )
    sources = research_archive_sources(content, report)
    content_verification_summary = content.get("claim_verification_summary")
    report_verification_summary = report.get("claim_verification_summary")
    raw_delivery_quality = report.get("delivery_quality")
    verification_summary = (
        dict(content_verification_summary)
        if isinstance(content_verification_summary, dict)
        else {}
    ) or (
        dict(report_verification_summary)
        if isinstance(report_verification_summary, dict)
        else {}
    )
    delivery_quality = (
        dict(raw_delivery_quality)
        if isinstance(raw_delivery_quality, dict)
        else {}
    )
    paragraph_citations = research_paragraph_citations(content, report)
    navigation_index = research_navigation_index(paragraph_citations)
    citation_graph = research_citation_graph(chains, sources, paragraph_citations)
    review_records = research_conflict_review_records(content)
    conflict_summary = research_conflict_summary(
        chains,
        review_records,
        archive_conflict_review=report.get("archive_conflict_review")
        if isinstance(report.get("archive_conflict_review"), dict)
        else None,
    )
    return {
        "archive_id": str(getattr(artifact, "artifact_id", "") or ""),
        "artifact_id": str(getattr(artifact, "artifact_id", "") or ""),
        "title": str(getattr(artifact, "title", "") or ""),
        "session_id": str(getattr(artifact, "session_id", "") or ""),
        "task_id": research_archive_task_id(artifact, content),
        "created_at": float(getattr(artifact, "created_at", 0) or 0),
        "updated_at": float(getattr(artifact, "updated_at", 0) or 0),
        "claim_count": len(chains),
        "source_count": len(sources),
        "verification_summary": verification_summary,
        "delivery_quality": delivery_quality,
        "preview_claims": research_claim_preview(chains, report),
        "preview_sources": research_source_preview(sources),
        "provider_capabilities": research_provider_capability_coverage(sources),
        "paragraph_citations": paragraph_citations,
        "paragraph_claim_links": navigation_index["links"],
        "navigation_index": navigation_index,
        "citation_graph": citation_graph,
        "conflict_summary": conflict_summary,
        "conflict_review_resolutions": review_records,
        "citation_panel": research_citation_panel_payload(
            chains,
            sources,
            verification_summary,
        ),
    }

def normalize_conflict_key_text(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()

def research_conflict_groups(archives: list[Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for artifact in archives:
        payload = research_archive_payload(artifact)
        artifact_id = str(payload.get("artifact_id") or "")
        title = str(payload.get("title") or "")
        for item in payload.get("conflict_summary", {}).get("items", []):
            if not isinstance(item, dict):
                continue
            source_ids = string_items(item.get("source_ids"))
            normalized_claim = normalize_conflict_key_text(
                item.get("claim_text") or item.get("claim_id")
            )
            normalized_source = normalize_conflict_key_text(" ".join(sorted(source_ids)))
            normalized_conflict = normalize_conflict_key_text(item.get("text"))
            key = (normalized_claim, normalized_source, normalized_conflict)
            group = groups.setdefault(
                key,
                {
                    "group_id": f"conflict-group-{len(groups) + 1}",
                    "normalized_claim": normalized_claim,
                    "normalized_source": normalized_source,
                    "normalized_conflict_text": normalized_conflict,
                    "conflict_text": str(item.get("text") or ""),
                    "claim_ids": [],
                    "source_ids": [],
                    "archives": [],
                    "review_statuses": [],
                    "total": 0,
                },
            )
            claim_id = str(item.get("claim_id") or "").strip()
            if claim_id and claim_id not in group["claim_ids"]:
                group["claim_ids"].append(claim_id)
            for source_id in source_ids:
                if source_id not in group["source_ids"]:
                    group["source_ids"].append(source_id)
            review_status = str(item.get("review_status") or "unreviewed").strip()
            if review_status not in group["review_statuses"]:
                group["review_statuses"].append(review_status)
            group["archives"].append(
                {
                    "artifact_id": artifact_id,
                    "archive_id": str(payload.get("archive_id") or artifact_id),
                    "title": title,
                    "claim_id": claim_id,
                    "conflict_id": str(item.get("conflict_id") or claim_id),
                    "review_status": review_status,
                }
            )
            group["total"] += 1
    return sorted(
        groups.values(),
        key=lambda group: (-int(group.get("total") or 0), str(group.get("group_id") or "")),
    )

def matches_research_archive_filters(
    artifact: Any,
    *,
    q: str,
    session_id: str,
    task_id: str,
) -> bool:
    content = artifact_content(artifact)
    report = research_report_content(artifact)
    chains = coerce_items(content.get("claim_evidence_chains")) or coerce_items(
        report.get("claim_evidence_chains")
    )
    sources = research_archive_sources(content, report)
    if session_id and str(getattr(artifact, "session_id", "") or "").strip() != session_id:
        return False
    if task_id and research_archive_task_id(artifact, content) != task_id:
        return False
    if q and q.lower() not in research_archive_search_text(
        artifact,
        content,
        report,
        sources,
        chains,
    ):
        return False
    return True
