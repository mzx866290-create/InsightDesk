"""Writing Agent for drafting and synthesizing workflow outputs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from backend.agent.protocols import AgentResult, AgentTask


WRITING_TEMPLATES: dict[str, dict[str, Any]] = {
    "default": {
        "style": "default",
        "title": "Writing Agent Draft",
        "sections": [
            "Request",
            "Executive Summary",
            "Key Findings",
            "Data Highlights",
            "Evidence And Sources",
            "Caveats And Next Steps",
        ],
    },
    "executive_brief": {
        "style": "executive",
        "title": "Executive Brief Draft",
        "sections": [
            "Request",
            "Bottom Line",
            "Key Signals",
            "Data Snapshot",
            "Evidence",
            "Risks And Next Steps",
        ],
    },
    "technical_report": {
        "style": "technical",
        "title": "Technical Report Draft",
        "sections": [
            "Objective",
            "Method",
            "Findings",
            "Data Analysis",
            "Sources",
            "Limitations And Next Steps",
        ],
    },
    "email_update": {
        "style": "email",
        "title": "Email Update Draft",
        "sections": [
            "Subject",
            "Update",
            "What We Learned",
            "Metrics",
            "Sources",
            "Asks And Next Steps",
        ],
    },
    "decision_memo": {
        "style": "decision",
        "title": "Decision Memo Draft",
        "sections": [
            "Decision Context",
            "Recommendation",
            "Rationale",
            "Data Considerations",
            "Evidence",
            "Risks And Next Steps",
        ],
    },
}


@dataclass(slots=True)
class WritingAgentConfig:
    timeout_seconds: float = 90.0
    max_context_chars: int = 8000
    metadata: dict[str, Any] = field(default_factory=dict)


class WritingAgent:
    """Drafts a usable narrative from upstream agent outputs."""

    name = "writing"
    description = "Writing Agent for drafting, rewriting, and synthesis."
    capabilities = ["writing", "draft", "summarize", "report", "synthesis"]

    def __init__(
        self,
        *,
        llm: Any | None = None,
        config: WritingAgentConfig | None = None,
    ) -> None:
        self.llm = llm
        self.config = config or WritingAgentConfig()

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        request = self._request_text(task)
        upstream = self._collect_upstream_context(context)
        source_text = self._render_upstream_context(upstream)
        template_id = self._select_template(task, context)
        template = WRITING_TEMPLATES[template_id]
        outline_agreement = self._negotiate_outline(task, context, template)
        fact_check = self._fact_check_loop(upstream)
        if self.llm is None:
            output = self._fallback_draft(request, upstream, template_id, outline_agreement, fact_check)
        else:
            output = await self._draft_with_llm(
                request,
                source_text,
                upstream,
                template_id,
                outline_agreement,
                fact_check,
            )
        output, style_correction = self._style_correction_loop(output, str(template["style"]))

        artifacts: list[dict[str, Any]] = [
            {
                "type": "markdown",
                "title": "Draft",
                "content": output,
            }
        ]
        metadata = {
            **self.config.metadata,
            "context_keys": sorted(context.keys()),
            "used_llm": self.llm is not None,
            "template": template_id,
            "style": str(template["style"]),
            "template_sections": list(template["sections"]),
            "upstream_agents": [item["agent"] for item in upstream],
            "research_artifacts": sum(1 for item in upstream if item["agent"] == "research"),
            "data_analysis_artifacts": sum(1 for item in upstream if item["agent"] == "data_analysis"),
            "outline_agreement": outline_agreement,
            "fact_check": fact_check,
            "style_correction": style_correction,
        }
        if self._requests_deck_json(task, context):
            deck_json = self._deck_json_artifact(
                request=request,
                upstream=upstream,
                template_id=template_id,
                style=str(template["style"]),
            )
            artifacts.append(
                {
                    "type": "deck_json",
                    "title": deck_json["title"],
                    "content": deck_json,
                }
            )
            metadata["deck_json_generated"] = True
            metadata["deck_slide_count"] = len(deck_json["slides"])

        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": output,
            "artifacts": artifacts,
            "sources": self._upstream_sources(context),
            "metadata": metadata,
        }

    @staticmethod
    def _request_text(task: AgentTask) -> str:
        raw_input = task.get("input")
        if isinstance(raw_input, str) and raw_input.strip():
            return raw_input.strip()
        return str(task.get("description") or "").strip()

    def _upstream_text(self, context: dict[str, Any]) -> str:
        return self._render_upstream_context(self._collect_upstream_context(context))

    @staticmethod
    def _select_template(task: AgentTask, context: dict[str, Any]) -> str:
        task_metadata = task.get("metadata")
        candidates: list[Any] = []
        if isinstance(task_metadata, dict):
            candidates.extend(
                [
                    task_metadata.get("writing_template"),
                    task_metadata.get("template"),
                    task_metadata.get("writing_style"),
                    task_metadata.get("style"),
                ]
            )
        candidates.extend(
            [
                context.get("writing_template"),
                context.get("template"),
                context.get("writing_style"),
                context.get("style"),
            ]
        )
        for candidate in candidates:
            template_id = str(candidate or "").strip().lower().replace("-", "_")
            if template_id in WRITING_TEMPLATES:
                return template_id
        return "default"

    @staticmethod
    def _requests_deck_json(task: AgentTask, context: dict[str, Any]) -> bool:
        deck_tokens = {"deck", "deck_json"}
        fields = ("output_format", "delivery_format", "artifact_type")
        task_metadata = task.get("metadata")
        candidates: list[Any] = []
        if isinstance(task_metadata, dict):
            candidates.extend(task_metadata.get(field) for field in fields)
        candidates.extend(context.get(field) for field in fields)
        for candidate in candidates:
            if isinstance(candidate, list | tuple | set):
                values = candidate
            else:
                values = [candidate]
            for value in values:
                normalized = str(value or "").strip().lower().replace("-", "_")
                if normalized in deck_tokens:
                    return True
        return False

    def _collect_upstream_context(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        results = context.get("_agent_results")
        if not isinstance(results, dict):
            return []
        upstream: list[dict[str, Any]] = []
        for result in results.values():
            if not isinstance(result, dict):
                continue
            agent = str(result.get("agent") or "agent").strip()
            output = str(result.get("output") or "").strip()
            artifacts = result.get("artifacts")
            upstream.append(
                {
                    "agent": agent,
                    "output": output,
                    "artifacts": [item for item in artifacts if isinstance(item, dict)]
                    if isinstance(artifacts, list)
                    else [],
                    "sources": result.get("sources") if isinstance(result.get("sources"), list) else [],
                    "metadata": result.get("metadata") if isinstance(result.get("metadata"), dict) else {},
                }
            )
        return upstream

    def _render_upstream_context(self, upstream: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for item in upstream:
            agent = str(item.get("agent") or "agent").strip()
            output = str(item.get("output") or "").strip()
            artifact_notes = self._artifact_notes(item)
            body = "\n\n".join(part for part in (output, artifact_notes) if part).strip()
            if body:
                parts.append(f"## {agent}\n{body}")
        text = "\n\n".join(parts).strip()
        limit = max(1000, int(self.config.max_context_chars))
        return text[:limit].strip()

    @staticmethod
    def _upstream_sources(context: dict[str, Any]) -> list[dict[str, Any]]:
        results = context.get("_agent_results")
        if not isinstance(results, dict):
            return []
        sources: list[dict[str, Any]] = []
        seen: set[str] = set()
        for result in results.values():
            if not isinstance(result, dict):
                continue
            raw_sources = result.get("sources")
            if not isinstance(raw_sources, list):
                continue
            for raw_source in raw_sources:
                if not isinstance(raw_source, dict):
                    continue
                key = str(raw_source.get("url") or raw_source.get("title") or raw_source)
                if key in seen:
                    continue
                seen.add(key)
                sources.append(dict(raw_source))
        return sources

    def _fallback_draft(
        self,
        request: str,
        upstream: list[dict[str, Any]],
        template_id: str = "default",
        outline_agreement: dict[str, Any] | None = None,
        fact_check: dict[str, Any] | None = None,
    ) -> str:
        research_sections = self._research_sections(upstream)
        data_sections = self._data_sections(upstream)
        source_notes = self._source_notes(upstream)
        template = WRITING_TEMPLATES.get(template_id, WRITING_TEMPLATES["default"])
        outline_agreement = outline_agreement or self._default_outline_agreement(template)
        fact_check = fact_check or {"claims": [], "unsupported_claims": [], "summary": "No claims to check."}

        if template_id != "default":
            return self._render_template_draft(
                request=request,
                upstream=upstream,
                template=template,
                research_sections=research_sections,
                data_sections=data_sections,
                source_notes=source_notes,
                outline_agreement=outline_agreement,
                fact_check=fact_check,
            )

        lines = [
            "# Writing Agent Draft",
            "",
            "## Request",
            request or "No request provided.",
            "",
            "## Outline Agreement",
        ]
        lines.extend(self._outline_notes(outline_agreement))
        lines.extend(
            [
                "",
                "## Executive Summary",
                self._executive_summary(research_sections, data_sections, upstream),
                "",
                "## Key Findings",
            ]
        )
        lines.extend(research_sections["findings"] or ["- No research findings were provided."])
        if data_sections["findings"]:
            lines.extend(data_sections["findings"])

        lines.extend(["", "## Data Highlights"])
        lines.extend(data_sections["highlights"] or ["- No structured data analysis artifact was provided."])

        lines.extend(["", "## Evidence And Sources"])
        lines.extend(source_notes or ["- No upstream sources were provided."])

        lines.extend(["", "## Fact Check"])
        lines.extend(self._fact_check_notes(fact_check))

        lines.extend(["", "## Caveats And Next Steps"])
        lines.extend(research_sections["caveats"] or [])
        lines.extend(data_sections["caveats"] or [])
        lines.extend(self._unsupported_claim_notes(fact_check))
        if not research_sections["caveats"] and not data_sections["caveats"]:
            lines.append("- Validate any unsupported claims before external publication.")

        return "\n".join(lines).strip()

    def _render_template_draft(
        self,
        *,
        request: str,
        upstream: list[dict[str, Any]],
        template: dict[str, Any],
        research_sections: dict[str, list[str]],
        data_sections: dict[str, list[str]],
        source_notes: list[str],
        outline_agreement: dict[str, Any],
        fact_check: dict[str, Any],
    ) -> str:
        sections = [str(section) for section in (outline_agreement.get("selected_sections") or template["sections"])]
        summary = self._executive_summary(research_sections, data_sections, upstream)
        caveats = research_sections["caveats"] + data_sections["caveats"]
        caveats += self._unsupported_claim_notes(fact_check)
        if not caveats:
            caveats = ["- Validate any unsupported claims before external publication."]

        section_content: dict[str, list[str]] = {
            "Request": [request or "No request provided."],
            "Objective": [request or "No request provided."],
            "Subject": [f"Subject: {request or 'Writing update'}"],
            "Decision Context": [request or "No decision context provided."],
            "Bottom Line": [summary],
            "Update": [summary],
            "Recommendation": [summary],
            "Method": [
                "This draft synthesizes available upstream research and data-analysis artifacts without calling an LLM."
            ],
            "Key Signals": research_sections["findings"] or ["- No research findings were provided."],
            "Findings": research_sections["findings"] or ["- No research findings were provided."],
            "What We Learned": research_sections["findings"] or ["- No research findings were provided."],
            "Rationale": (research_sections["findings"] or ["- No research findings were provided."])
            + (data_sections["findings"] or []),
            "Data Snapshot": data_sections["highlights"]
            or ["- No structured data analysis artifact was provided."],
            "Data Analysis": data_sections["highlights"]
            or ["- No structured data analysis artifact was provided."],
            "Metrics": data_sections["highlights"]
            or ["- No structured data analysis artifact was provided."],
            "Data Considerations": data_sections["highlights"]
            or ["- No structured data analysis artifact was provided."],
            "Evidence": source_notes or ["- No upstream sources were provided."],
            "Sources": source_notes or ["- No upstream sources were provided."],
            "Risks And Next Steps": caveats,
            "Limitations And Next Steps": caveats,
            "Asks And Next Steps": caveats,
            "Outline Agreement": self._outline_notes(outline_agreement),
            "Fact Check": self._fact_check_notes(fact_check),
        }

        lines = [f"# {template['title']}"]
        for section in ("Outline Agreement", "Fact Check"):
            if section not in sections:
                sections.append(section)
        for section in sections:
            lines.extend(["", f"## {section}"])
            lines.extend(
                self._section_body(
                    section=section,
                    section_content=section_content,
                    request=request,
                    summary=summary,
                    research_sections=research_sections,
                    data_sections=data_sections,
                    source_notes=source_notes,
                    caveats=caveats,
                )
            )
        return "\n".join(lines).strip()

    async def _draft_with_llm(
        self,
        request: str,
        source_text: str,
        upstream: list[dict[str, Any]],
        template_id: str = "default",
        outline_agreement: dict[str, Any] | None = None,
        fact_check: dict[str, Any] | None = None,
    ) -> str:
        template = WRITING_TEMPLATES.get(template_id, WRITING_TEMPLATES["default"])
        negotiated_outline = outline_agreement or self._default_outline_agreement(template)
        sections = ", ".join(str(section) for section in (negotiated_outline.get("selected_sections") or template["sections"]))
        outline_notes = "\n".join(self._outline_notes(negotiated_outline))
        fact_check_notes = "\n".join(
            self._fact_check_notes(fact_check or {"claims": [], "unsupported_claims": []})
        )
        prompt = (
            "You are a writing agent. Produce a concise, structured Markdown draft.\n"
            "Use only the provided upstream research and data-analysis artifacts when they exist.\n"
            "Resolve outline disagreements explicitly and label unsupported claims.\n"
            f"Use the {template_id} template and include these sections: {sections}.\n\n"
            f"Outline agreement:\n{outline_notes}\n\n"
            f"Fact-check loop:\n{fact_check_notes}\n\n"
            f"User request:\n{request}\n\n"
            f"Upstream findings:\n{source_text or '[none]'}"
        )
        response = await asyncio.wait_for(
            self.llm.ainvoke(prompt),
            timeout=max(1.0, float(self.config.timeout_seconds)),
        )
        return str(getattr(response, "content", response) or "").strip() or self._fallback_draft(
            request,
            upstream,
            template_id,
            negotiated_outline,
            fact_check,
        )

    def _section_body(
        self,
        *,
        section: str,
        section_content: dict[str, list[str]],
        request: str,
        summary: str,
        research_sections: dict[str, list[str]],
        data_sections: dict[str, list[str]],
        source_notes: list[str],
        caveats: list[str],
    ) -> list[str]:
        content = section_content.get(section)
        if content:
            return content

        normalized = section.strip().lower()
        if normalized in {"audience", "target audience"}:
            return [f"- Audience inferred from request: {request or 'Not specified.'}"]
        if normalized in {"summary", "executive summary", "bottom line", "recommendation", "decision"}:
            return [summary]
        if normalized in {"request", "objective"}:
            return [request or "No request provided."]
        if normalized in {"risks and next steps", "limitations and next steps", "asks and next steps"}:
            return caveats or ["- Validate any unsupported claims before external publication."]
        if normalized in {"evidence", "sources"}:
            return source_notes or ["- No upstream sources were provided."]
        if normalized in {"findings", "key signals", "what we learned", "rationale"}:
            return research_sections["findings"] or ["- No research findings were provided."]
        if "data" in normalized or "metrics" in normalized:
            return data_sections["highlights"] or ["- No structured data analysis artifact was provided."]
        return [f"- No source-backed content available for {section}."]

    @staticmethod
    def _artifact_notes(item: dict[str, Any]) -> str:
        notes: list[str] = []
        for artifact in item.get("artifacts", []):
            artifact_type = str(artifact.get("type") or "")
            content = artifact.get("content", artifact)
            if artifact_type in {"query_result", "chart_spec", "dashboard_card"}:
                notes.append(f"- {artifact.get('title') or artifact_type}: {content}")
            elif artifact_type in {"json", "research_report"}:
                notes.append(f"- {artifact.get('title') or artifact_type}: {content}")
        return "\n".join(notes)

    def _research_sections(self, upstream: list[dict[str, Any]]) -> dict[str, list[str]]:
        findings: list[str] = []
        caveats: list[str] = []
        for item in upstream:
            if item.get("agent") != "research":
                continue
            for artifact in item.get("artifacts", []):
                if artifact.get("type") != "research_report":
                    continue
                highlights = artifact.get("highlights")
                if isinstance(highlights, list):
                    findings.extend(f"- {self._plain_text(value)}" for value in highlights[:6] if self._plain_text(value))
                summary = self._plain_text(artifact.get("summary"))
                if summary and not findings:
                    findings.append(f"- {summary}")
                for caveat in artifact.get("caveats", []) if isinstance(artifact.get("caveats"), list) else []:
                    text = self._plain_text(caveat)
                    if text:
                        caveats.append(f"- {text}")
            output = self._plain_text(item.get("output"))
            if output and not findings:
                findings.append(f"- {output[:500]}")
        return {"findings": findings, "caveats": caveats}

    def _data_sections(self, upstream: list[dict[str, Any]]) -> dict[str, list[str]]:
        findings: list[str] = []
        highlights: list[str] = []
        caveats: list[str] = []
        for item in upstream:
            if item.get("agent") != "data_analysis":
                continue
            for artifact in item.get("artifacts", []):
                artifact_type = str(artifact.get("type") or "")
                content = artifact.get("content")
                if artifact_type == "json" and isinstance(content, dict):
                    highlights.extend(self._profile_highlights(content))
                elif artifact_type == "query_result" and isinstance(content, dict):
                    findings.extend(self._query_findings(content))
                elif artifact_type == "chart_spec" and isinstance(content, dict):
                    metric = self._plain_text(content.get("metric") or "metric")
                    dimension = self._plain_text(content.get("dimension") or "dimension")
                    chart_type = self._plain_text(content.get("type") or "chart")
                    highlights.append(f"- Suggested {chart_type} chart: {metric} by {dimension}.")
            output = self._plain_text(item.get("output"))
            if output and not highlights:
                highlights.append(f"- {output[:500]}")
        if not findings and highlights:
            findings.append("- Data analysis artifacts are available and summarized below.")
        if not any(item.get("agent") == "data_analysis" for item in upstream):
            caveats.append("- Add data-analysis results if numerical validation is required.")
        return {"findings": findings, "highlights": highlights, "caveats": caveats}

    @staticmethod
    def _profile_highlights(profile: dict[str, Any]) -> list[str]:
        rows = profile.get("row_count", 0)
        columns = profile.get("column_count", 0)
        highlights = [f"- Dataset profile: {rows} rows across {columns} columns."]
        numeric_columns = profile.get("numeric_columns")
        if isinstance(numeric_columns, dict):
            for column, stats in list(numeric_columns.items())[:3]:
                if isinstance(stats, dict):
                    highlights.append(
                        f"- {column}: sum={stats.get('sum')}, mean={stats.get('mean')}, "
                        f"range={stats.get('min')} to {stats.get('max')}."
                    )
        return highlights

    @staticmethod
    def _query_findings(query_result: dict[str, Any]) -> list[str]:
        metric = str(query_result.get("metric") or "value")
        dimension = str(query_result.get("dimension") or "")
        rows = query_result.get("rows")
        if not isinstance(rows, list) or not rows:
            return ["- Query result returned no matching rows."]
        findings: list[str] = []
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            label = row.get("dimension") if dimension else row.get(metric, "")
            value = row.get("value", row.get(metric, ""))
            findings.append(f"- {dimension or metric} {label}: {value}.")
        return findings

    def _source_notes(self, upstream: list[dict[str, Any]]) -> list[str]:
        notes: list[str] = []
        for item in upstream:
            agent = str(item.get("agent") or "agent")
            sources = item.get("sources")
            if not isinstance(sources, list):
                continue
            for source in sources[:8]:
                if not isinstance(source, dict):
                    continue
                title = self._plain_text(source.get("title") or source.get("url") or source.get("type"))
                if title:
                    notes.append(f"- {agent}: {title}")
        return notes

    @staticmethod
    def _default_outline_agreement(template: dict[str, Any]) -> dict[str, Any]:
        sections = [str(section) for section in template["sections"]]
        return {
            "requested_sections": [],
            "selected_sections": sections,
            "added_sections": sections,
            "omitted_sections": [],
            "status": "template_default",
            "notes": ["No custom outline was provided; using the selected writing template."],
        }

    def _negotiate_outline(
        self,
        task: AgentTask,
        context: dict[str, Any],
        template: dict[str, Any],
    ) -> dict[str, Any]:
        requested = self._requested_outline_sections(task, context)
        template_sections = [str(section) for section in template["sections"]]
        if not requested:
            return self._default_outline_agreement(template)

        selected: list[str] = []
        for section in requested + template_sections:
            normalized = self._plain_text(section)
            if normalized and normalized.lower() not in {item.lower() for item in selected}:
                selected.append(normalized)

        requested_lookup = {section.lower() for section in requested}
        selected_lookup = {section.lower() for section in selected}
        added = [section for section in selected if section.lower() not in requested_lookup]
        omitted = [section for section in requested if section.lower() not in selected_lookup]
        status = "accepted" if not added and not omitted else "merged"
        notes = [
            "Custom outline was accepted and merged with required template sections."
            if status == "merged"
            else "Custom outline was accepted as provided."
        ]
        if added:
            notes.append("Added template sections to preserve evidence, caveats, and next steps.")
        if omitted:
            notes.append("Omitted empty or duplicate requested sections.")

        return {
            "requested_sections": requested,
            "selected_sections": selected,
            "added_sections": added,
            "omitted_sections": omitted,
            "status": status,
            "notes": notes,
        }

    def _requested_outline_sections(self, task: AgentTask, context: dict[str, Any]) -> list[str]:
        candidates: list[Any] = []
        task_metadata = task.get("metadata")
        if isinstance(task_metadata, dict):
            candidates.extend(
                [
                    task_metadata.get("outline"),
                    task_metadata.get("outline_sections"),
                    task_metadata.get("proposed_outline"),
                ]
            )
        candidates.extend(
            [
                context.get("outline"),
                context.get("outline_sections"),
                context.get("proposed_outline"),
            ]
        )
        for candidate in candidates:
            sections = self._coerce_outline_sections(candidate)
            if sections:
                return sections
        return []

    def _coerce_outline_sections(self, value: Any) -> list[str]:
        if isinstance(value, str):
            raw_parts = value.replace("\r", "\n").split("\n")
            sections = []
            for raw_part in raw_parts:
                section = raw_part.strip().lstrip("-0123456789. )\t")
                if section:
                    sections.append(section)
            return sections
        if isinstance(value, list | tuple):
            sections: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    text = self._plain_text(item.get("title") or item.get("section") or item.get("name"))
                else:
                    text = self._plain_text(item)
                if text:
                    sections.append(text)
            return sections
        return []

    @staticmethod
    def _outline_notes(outline_agreement: dict[str, Any]) -> list[str]:
        selected = outline_agreement.get("selected_sections")
        added = outline_agreement.get("added_sections")
        notes = outline_agreement.get("notes")
        lines = [f"- Status: {outline_agreement.get('status', 'unknown')}."]
        if isinstance(selected, list) and selected:
            lines.append("- Final outline: " + " > ".join(str(section) for section in selected) + ".")
        if isinstance(added, list) and added:
            lines.append("- Added sections: " + ", ".join(str(section) for section in added) + ".")
        if isinstance(notes, list):
            lines.extend(f"- {note}" for note in notes if str(note).strip())
        return lines

    def _fact_check_loop(self, upstream: list[dict[str, Any]]) -> dict[str, Any]:
        claims: list[dict[str, Any]] = []
        for item in upstream:
            agent = str(item.get("agent") or "agent")
            source_titles = self._source_titles(item)
            for claim in self._claim_candidates(item):
                claims.append(
                    {
                        "claim": claim,
                        "agent": agent,
                        "status": "supported" if source_titles else "needs_source",
                        "evidence": source_titles[:3],
                    }
                )

        unsupported = [claim for claim in claims if claim["status"] != "supported"]
        if not claims:
            summary = "No upstream claims were available for fact checking."
        elif unsupported:
            summary = f"{len(unsupported)} of {len(claims)} claims need source confirmation."
        else:
            summary = f"All {len(claims)} extracted claims have upstream source references."

        return {
            "claims": claims,
            "unsupported_claims": unsupported,
            "summary": summary,
        }

    def _claim_candidates(self, item: dict[str, Any]) -> list[str]:
        claims: list[str] = []
        for artifact in item.get("artifacts", []):
            if not isinstance(artifact, dict):
                continue
            if artifact.get("type") == "research_report":
                summary = self._plain_text(artifact.get("summary"))
                if summary:
                    claims.append(summary)
                highlights = artifact.get("highlights")
                if isinstance(highlights, list):
                    claims.extend(self._plain_text(value) for value in highlights if self._plain_text(value))
            content = artifact.get("content")
            if artifact.get("type") == "query_result" and isinstance(content, dict):
                claims.extend(line.lstrip("- ").rstrip(".") for line in self._query_findings(content))
            elif artifact.get("type") == "json" and isinstance(content, dict):
                claims.extend(line.lstrip("- ").rstrip(".") for line in self._profile_highlights(content)[:3])
        output = self._plain_text(item.get("output"))
        if output and not claims:
            claims.append(output[:240])
        return claims[:8]

    def _source_titles(self, item: dict[str, Any]) -> list[str]:
        sources = item.get("sources")
        if not isinstance(sources, list):
            return []
        titles: list[str] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            title = self._plain_text(source.get("title") or source.get("url") or source.get("type"))
            if title:
                titles.append(title)
        return titles

    @staticmethod
    def _fact_check_notes(fact_check: dict[str, Any]) -> list[str]:
        claims = fact_check.get("claims")
        if not isinstance(claims, list) or not claims:
            return ["- No upstream claims were available for fact checking."]
        lines = [f"- Summary: {fact_check.get('summary', 'Fact check completed.')}"]
        for claim in claims[:6]:
            if not isinstance(claim, dict):
                continue
            evidence = claim.get("evidence")
            evidence_text = ", ".join(str(item) for item in evidence) if isinstance(evidence, list) and evidence else "missing source"
            lines.append(f"- {claim.get('status', 'unknown')}: {claim.get('claim', '')} (evidence: {evidence_text}).")
        return lines

    @staticmethod
    def _unsupported_claim_notes(fact_check: dict[str, Any]) -> list[str]:
        unsupported = fact_check.get("unsupported_claims")
        if not isinstance(unsupported, list):
            return []
        notes: list[str] = []
        for claim in unsupported[:4]:
            if isinstance(claim, dict) and claim.get("claim"):
                notes.append(f"- Confirm source support before publishing: {claim['claim']}")
        return notes

    def _style_correction_loop(self, output: str, style: str) -> tuple[str, dict[str, Any]]:
        corrected = output.strip()
        changes: list[str] = []
        if "\n\n\n" in corrected:
            while "\n\n\n" in corrected:
                corrected = corrected.replace("\n\n\n", "\n\n")
            changes.append("collapsed_extra_blank_lines")

        if style == "executive":
            corrected, changed = self._trim_bullet_length(corrected, max_chars=180)
            if changed:
                changes.append("trimmed_executive_bullets")
        elif style == "email" and not corrected.startswith("Subject:") and "\n## Subject\nSubject:" in corrected:
            corrected = corrected.replace("\n## Subject\nSubject:", "\n## Subject\n", 1)
            changes.append("deduplicated_email_subject_label")

        return corrected, {
            "status": "corrected" if changes else "passed",
            "style": style,
            "changes": changes,
        }

    @staticmethod
    def _trim_bullet_length(output: str, max_chars: int) -> tuple[str, bool]:
        changed = False
        lines: list[str] = []
        for line in output.splitlines():
            if line.startswith("- ") and len(line) > max_chars:
                lines.append(line[: max_chars - 3].rstrip() + "...")
                changed = True
            else:
                lines.append(line)
        return "\n".join(lines), changed

    def _deck_json_artifact(
        self,
        *,
        request: str,
        upstream: list[dict[str, Any]],
        template_id: str,
        style: str,
    ) -> dict[str, Any]:
        research_sections = self._research_sections(upstream)
        data_sections = self._data_sections(upstream)
        source_registry = self._deck_source_registry(upstream)
        default_refs = [source["id"] for source in source_registry[:3]]
        title = request or WRITING_TEMPLATES[template_id]["title"]

        slides: list[dict[str, Any]] = [
            self._deck_slide(
                slide_id="slide-1",
                slide_type="title",
                title=title,
                blocks=[
                    {
                        "type": "text",
                        "text": self._executive_summary(research_sections, data_sections, upstream),
                    }
                ],
                evidence_refs=default_refs,
            )
        ]

        key_points = self._deck_points(
            research_sections["findings"],
            fallback=["No upstream research findings were provided."],
        )
        slides.append(
            self._deck_slide(
                slide_id="slide-2",
                slide_type="summary",
                title="Summary",
                blocks=[{"type": "bullet_list", "items": key_points}],
                evidence_refs=default_refs,
            )
        )

        data_points = self._deck_points(data_sections["highlights"] + data_sections["findings"])
        if data_points:
            slides.append(
                self._deck_slide(
                    slide_id=f"slide-{len(slides) + 1}",
                    slide_type="content",
                    title="Data Highlights",
                    blocks=[{"type": "bullet_list", "items": data_points}],
                    evidence_refs=default_refs,
                )
            )

        next_steps = self._deck_points(
            research_sections["caveats"] + data_sections["caveats"],
            fallback=["Validate unsupported claims before external publication."],
        )
        slides.append(
            self._deck_slide(
                slide_id=f"slide-{len(slides) + 1}",
                slide_type="next_steps",
                title="Next Steps",
                blocks=[{"type": "bullet_list", "items": next_steps}],
                evidence_refs=default_refs,
            )
        )

        return {
            "version": "1.0",
            "title": title,
            "slides": slides,
            "source_registry": source_registry,
            "generation": {
                "source": "writing_agent",
                "template": template_id,
                "style": style,
            },
        }

    @staticmethod
    def _deck_slide(
        *,
        slide_id: str,
        slide_type: str,
        title: str,
        blocks: list[dict[str, Any]],
        evidence_refs: list[str],
    ) -> dict[str, Any]:
        return {
            "id": slide_id,
            "type": slide_type,
            "title": title,
            "blocks": blocks,
            "evidence_refs": evidence_refs,
            "quality_state": "draft",
        }

    @staticmethod
    def _deck_points(items: list[str], fallback: list[str] | None = None) -> list[str]:
        points = [item.lstrip("- ").strip() for item in items if item.lstrip("- ").strip()]
        if points:
            return points[:5]
        return list(fallback or [])

    def _deck_source_registry(self, upstream: list[dict[str, Any]]) -> list[dict[str, Any]]:
        registry: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in upstream:
            agent = str(item.get("agent") or "agent")
            sources = item.get("sources")
            if not isinstance(sources, list):
                continue
            for source in sources:
                if not isinstance(source, dict):
                    continue
                key = self._plain_text(source.get("url") or source.get("title") or source.get("type"))
                if not key or key in seen:
                    continue
                seen.add(key)
                source_id = f"src-{len(registry) + 1}"
                registry.append(
                    {
                        "id": source_id,
                        "agent": agent,
                        "title": self._plain_text(source.get("title") or key),
                        "url": self._plain_text(source.get("url")),
                        "type": self._plain_text(source.get("type")),
                    }
                )
        return registry

    @staticmethod
    def _executive_summary(
        research_sections: dict[str, list[str]],
        data_sections: dict[str, list[str]],
        upstream: list[dict[str, Any]],
    ) -> str:
        if research_sections["findings"] and data_sections["highlights"]:
            return "This draft combines upstream research findings with structured data-analysis artifacts."
        if research_sections["findings"]:
            return "This draft is based on upstream research findings and source notes."
        if data_sections["highlights"]:
            return "This draft is based on upstream structured data-analysis artifacts."
        if upstream:
            return "This draft summarizes available upstream workflow output."
        return "No upstream artifacts were provided; the draft only reflects the request."

    @staticmethod
    def _plain_text(value: Any) -> str:
        return str(value or "").strip().replace("\n", " ")


__all__ = ["WritingAgent", "WritingAgentConfig"]
