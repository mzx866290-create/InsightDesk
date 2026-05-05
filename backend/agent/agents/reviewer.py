"""Review Agent for quality checks over workflow outputs."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from backend.agent.protocols import AgentResult, AgentTask


@dataclass(slots=True)
class ReviewAgentConfig:
    timeout_seconds: float = 90.0
    max_context_chars: int = 8000
    checklist: list[str] = field(default_factory=list)
    review_policy: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ReviewAgent:
    """Reviews upstream outputs for risks, gaps, and follow-up actions."""

    name = "review"
    description = "QA Agent for quality review and risk checks."
    capabilities = ["review", "qa", "quality", "risk", "fact_check"]

    def __init__(
        self,
        *,
        llm: Any | None = None,
        config: ReviewAgentConfig | None = None,
    ) -> None:
        self.llm = llm
        self.config = config or ReviewAgentConfig()

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        request = str(task.get("input") or task.get("description") or task.get("title") or "").strip()
        upstream = self._collect_upstream_results(context)
        checklist = self._resolve_checklist(task, context)
        review_policy = self._resolve_review_policy(task, context)
        review_payload = self._build_quality_gate(request, upstream, checklist, review_policy)

        source_text = self._render_upstream_context(upstream)
        output = self._render_review_markdown(review_payload)
        if self.llm is not None and hasattr(self.llm, "ainvoke"):
            try:
                output = await self._review_with_llm(request, source_text, review_payload)
            except Exception:
                output = self._render_review_markdown(review_payload)

        return {
            "agent": self.name,
            "task_id": task.get("id"),
            "task_type": task.get("type") or task.get("task_type") or "review",
            "status": "completed",
            "output": output,
            "artifacts": [
                {
                    "type": "quality_gate",
                    "title": "Quality gate",
                    "content": review_payload,
                },
                {
                    "type": "approval_recommendation",
                    "title": "Approval recommendation",
                    "content": review_payload["approval_recommendation"],
                }
            ],
            "sources": [],
            "metadata": {
                "quality_gate": review_payload["gate"],
                "passed": review_payload["passed"],
                "issue_count": len(review_payload["issues"]),
                "review_policy": review_payload["policy"],
                "approval_recommendation": review_payload["approval_recommendation"],
            },
        }

    @staticmethod
    def _collect_upstream_results(context: dict[str, Any]) -> list[dict[str, Any]]:
        raw_results = context.get("_agent_results") or context.get("agent_results") or {}
        if isinstance(raw_results, dict):
            return [dict(item) for item in raw_results.values() if isinstance(item, dict)]
        if isinstance(raw_results, list):
            return [dict(item) for item in raw_results if isinstance(item, dict)]
        return []

    def _render_upstream_context(self, upstream: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for item in upstream:
            agent = str(item.get("agent") or "agent")
            output = str(item.get("output") or "").strip()
            if output:
                parts.append(f"[{agent}]\n{output}")
            artifacts = item.get("artifacts")
            if isinstance(artifacts, list) and artifacts:
                artifact_types = ", ".join(str(artifact.get("type") or "unknown") for artifact in artifacts if isinstance(artifact, dict))
                if artifact_types:
                    parts.append(f"[{agent} artifacts] {artifact_types}")
        return "\n\n".join(parts)[: max(1, int(self.config.max_context_chars))]

    def _render_review_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "# QA Agent Review Report",
            "",
            "## Quality Gate",
            f"- Gate: {payload['gate']}",
            f"- Passed: {'yes' if payload['passed'] else 'no'}",
            f"- Confidence: {payload['confidence']}",
            "",
            "## Issues",
        ]
        issues = payload.get("issues") or []
        if issues:
            for issue in issues:
                lines.append(
                    f"- [{issue.get('severity', 'unknown')}] {issue.get('category', 'general')}: "
                    f"{issue.get('message', '')} Fix: {issue.get('fix', '')}"
                )
        else:
            lines.append("- No blocking issues found.")

        lines.extend(["", "## Checks"])
        for check in payload.get("checks") or []:
            lines.append(f"- {check.get('item')}: {check.get('status')} - {check.get('details')}")

        checklist = payload.get("checklist") or []
        if checklist:
            lines.extend(["", "## Checklist"])
            for item in checklist:
                lines.append(f"- {item.get('item')}: {item.get('status')}")

        lines.extend(["", "## Review Basis"])
        for item in payload.get("basis") or []:
            lines.append(f"- {item}")

        recommendation = payload.get("approval_recommendation")
        if isinstance(recommendation, dict):
            lines.extend(["", "## Approval Recommendation"])
            lines.append(f"- Decision: {recommendation.get('decision', 'needs_review')}")
            lines.append(f"- Reason: {recommendation.get('reason', '')}")
            if recommendation.get("requires_override"):
                lines.append("- Override: required for approval.")
        return "\n".join(lines).strip()

    async def _review_with_llm(
        self,
        request: str,
        source_text: str,
        review_payload: dict[str, Any],
    ) -> str:
        prompt = (
            "You are a QA review agent. Review the draft/findings for risks, missing evidence, "
            "contradictions, and concrete fixes. Return concise Markdown with sections: "
            "Quality Gate, Issues, Checks, Review Basis. State whether the deliverable passes.\n\n"
            f"Original request:\n{request}\n\n"
            f"Deterministic gate payload:\n{review_payload}\n\n"
            f"Workflow content:\n{source_text or '[none]'}"
        )
        response = await asyncio.wait_for(
            self.llm.ainvoke(prompt),
            timeout=max(1.0, float(self.config.timeout_seconds)),
        )
        return str(getattr(response, "content", response) or "").strip() or self._render_review_markdown(review_payload)

    def _build_quality_gate(
        self,
        request: str,
        upstream: list[dict[str, Any]],
        checklist: list[str] | None = None,
        review_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        checks: list[dict[str, str]] = []
        policy = self._normalize_review_policy(review_policy)

        has_upstream = bool(upstream)
        has_writing = any(item.get("agent") == "writing" and item.get("output") for item in upstream)
        has_research = any(item.get("agent") == "research" for item in upstream)
        has_data = any(item.get("agent") == "data_analysis" for item in upstream)
        has_sources = any(item.get("sources") for item in upstream)
        has_quality_artifact = any(
            artifact.get("type") in {"markdown", "research_report", "json", "query_result", "chart_spec"}
            for item in upstream
            for artifact in item.get("artifacts", [])
            if isinstance(artifact, dict)
        )

        if not has_upstream:
            issues.append(
                self._issue(
                    "blocker",
                    "coverage",
                    "No upstream deliverable or evidence was provided for review.",
                    "Run writing, research, or data_analysis before review.",
                )
            )
        if not has_writing:
            issues.append(
                self._issue(
                    "major",
                    "deliverable",
                    "No writing draft was found in upstream results.",
                    "Generate a markdown delivery draft before final QA.",
                )
            )
        if has_research and not has_sources:
            issues.append(
                self._issue(
                    "major",
                    "evidence",
                    "Research output exists but no source list was attached.",
                    "Attach source payloads or mark claims as unsupported.",
                )
            )
        if has_data and not has_quality_artifact:
            issues.append(
                self._issue(
                    "minor",
                    "data",
                    "Data analysis ran without reviewable structured artifacts.",
                    "Attach profile, query_result, or chart_spec artifacts.",
                )
            )

        traceability_issues = self._numeric_date_traceability_issues(upstream)
        issues.extend(traceability_issues)
        citation_issues = self._citation_consistency_issues(upstream, policy)
        issues.extend(citation_issues)

        checks.append(self._check("Upstream content", "pass" if has_upstream else "fail", "Review has workflow output."))
        checks.append(self._check("Markdown draft", "pass" if has_writing else "warn", "Writing deliverable is present."))
        checks.append(self._check("Evidence coverage", "pass" if has_sources or not has_research else "warn", "Sources are attached when research is used."))
        checks.append(self._check("Artifact coverage", "pass" if has_quality_artifact else "warn", "Structured artifacts are available for QA."))
        checks.append(
            self._check(
                "Number/date traceability",
                "warn" if traceability_issues else "pass",
                "Numbers and dates in writing are present in upstream evidence.",
            )
        )
        checks.append(
            self._check(
                "Citation consistency",
                "warn" if citation_issues else "pass",
                "Citation markers, source sections, and attached sources are aligned.",
            )
        )

        blocking = any(item["severity"] == "blocker" for item in issues)
        major_count = sum(1 for item in issues if item["severity"] == "major")
        major_limit = max(0, int(policy.get("max_major_issues_for_pass", 0)))
        passed = not blocking and major_count <= major_limit
        gate = "pass" if passed else "fail" if blocking else "needs_fix"

        return {
            "gate": gate,
            "passed": passed,
            "confidence": "medium" if has_upstream else "low",
            "issues": issues,
            "checks": checks,
            "checklist": self._render_checklist(checklist or []),
            "policy": policy,
            "citation_audit": self._citation_audit(upstream),
            "approval_recommendation": self._approval_recommendation(
                gate=gate,
                passed=passed,
                issues=issues,
                policy=policy,
            ),
            "basis": self._review_basis(request, upstream),
        }

    def _approval_recommendation(
        self,
        *,
        gate: str,
        passed: bool,
        issues: list[dict[str, str]],
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        blockers = [issue for issue in issues if issue.get("severity") == "blocker"]
        major_issues = [issue for issue in issues if issue.get("severity") == "major"]
        blocked_gates = {
            str(item).strip().lower()
            for item in policy.get("block_on_quality_gates", ["fail"])
            if str(item or "").strip()
        }
        requires_override = gate in blocked_gates and not passed
        if passed:
            decision = "approve"
            reason = "Quality gate passed."
        elif blockers:
            decision = "block"
            reason = f"{len(blockers)} blocker issue(s) must be resolved before approval."
        else:
            decision = "request_changes"
            reason = f"{len(major_issues)} major issue(s) need remediation before approval."

        return {
            "decision": decision,
            "gate": gate,
            "passed": passed,
            "requires_override": requires_override,
            "blocker_count": len(blockers),
            "major_issue_count": len(major_issues),
            "reason": reason,
            "next_actions": [
                str(issue.get("fix") or issue.get("message") or "").strip()
                for issue in issues[:5]
                if str(issue.get("fix") or issue.get("message") or "").strip()
            ],
        }

    def _resolve_checklist(self, task: AgentTask, context: dict[str, Any]) -> list[str]:
        metadata = task.get("metadata")
        candidates: list[Any] = []
        if isinstance(metadata, dict):
            candidates.extend([metadata.get("review_checklist"), metadata.get("checklist")])
        candidates.extend([context.get("review_checklist"), context.get("checklist"), self.config.checklist])
        for candidate in candidates:
            normalized = self._normalize_checklist(candidate)
            if normalized:
                return normalized
        return []

    def _resolve_review_policy(self, task: AgentTask, context: dict[str, Any]) -> dict[str, Any]:
        policy: dict[str, Any] = {}
        policy.update(self.config.review_policy)
        config_policy = self.config.metadata.get("review_policy") if isinstance(self.config.metadata, dict) else None
        if isinstance(config_policy, dict):
            policy.update(config_policy)
        context_policy = context.get("review_policy")
        if isinstance(context_policy, dict):
            policy.update(context_policy)
        metadata = task.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("review_policy"), dict):
            policy.update(metadata["review_policy"])
        return self._normalize_review_policy(policy)

    @staticmethod
    def _normalize_review_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(policy or {})
        return {
            "enforce_citation_map": bool(raw.get("enforce_citation_map", True)),
            "allow_uncited_sources": bool(raw.get("allow_uncited_sources", True)),
            "enforce_citation_support_alignment": bool(raw.get("enforce_citation_support_alignment", False)),
            "citation_support_min_overlap": float(raw.get("citation_support_min_overlap", 0.12) or 0.12),
            "max_major_issues_for_pass": int(raw.get("max_major_issues_for_pass", 0) or 0),
        }

    @staticmethod
    def _normalize_checklist(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("item") or item.get("name") or item.get("title") or "").strip()
            else:
                text = ""
            if text:
                items.append(text)
        return items

    @staticmethod
    def _render_checklist(checklist: list[str]) -> list[dict[str, str]]:
        return [{"item": item, "status": "configured"} for item in checklist]

    def _numeric_date_traceability_issues(self, upstream: list[dict[str, Any]]) -> list[dict[str, str]]:
        writing_text = "\n".join(
            str(item.get("output") or "") for item in upstream if item.get("agent") == "writing"
        )
        if not writing_text.strip():
            return []

        evidence_text = self._evidence_text_for_traceability(upstream)
        missing = [token for token in self._extract_numeric_date_tokens(writing_text) if token not in evidence_text]
        if not missing:
            return []

        preview = ", ".join(missing[:6])
        suffix = "" if len(missing) <= 6 else f" and {len(missing) - 6} more"
        return [
            self._issue(
                "major",
                "evidence",
                f"Writing output contains number/date values not found in upstream evidence: {preview}{suffix}.",
                "Add supporting source/artifact text for these values or remove the unsupported claims.",
            )
        ]

    def _citation_consistency_issues(
        self,
        upstream: list[dict[str, Any]],
        policy: dict[str, Any],
    ) -> list[dict[str, str]]:
        writing_text = "\n".join(
            str(item.get("output") or "") for item in upstream if item.get("agent") == "writing"
        )
        if not writing_text.strip() or not self._has_citation_signal(writing_text):
            return []

        audit = self._citation_audit(upstream)
        cited_refs = set(audit["cited_refs"])
        source_section_refs = set(audit["source_section_refs"])
        attached_source_refs = set(audit["attached_source_refs"])
        fallback_refs = {str(index) for index in range(1, int(audit["attached_source_count"]) + 1)}
        available_refs = source_section_refs | attached_source_refs | fallback_refs
        issues: list[dict[str, str]] = []

        if not available_refs:
            return [
                self._issue(
                    "major",
                    "source",
                    "Writing output includes citation markers or a source section, but no sources are attached.",
                    "Attach the cited sources or remove citation markers until evidence is available.",
                )
            ]

        if bool(policy.get("enforce_citation_map", True)) and cited_refs:
            dangling_refs = sorted(cited_refs - available_refs, key=self._citation_sort_key)
            if dangling_refs:
                issues.append(
                    self._issue(
                        "major",
                        "source",
                        f"Writing output cites references with no matching source entry: {', '.join(dangling_refs)}.",
                        "Add matching source entries or renumber/remove the dangling citation markers.",
                    )
                )

        if not bool(policy.get("allow_uncited_sources", True)) and source_section_refs:
            uncited_refs = sorted(source_section_refs - cited_refs, key=self._citation_sort_key)
            if uncited_refs:
                issues.append(
                    self._issue(
                        "minor",
                        "source",
                        f"Source section contains uncited references: {', '.join(uncited_refs)}.",
                        "Cite these sources in the draft or remove unused source entries.",
                    )
                )

        if bool(policy.get("enforce_citation_support_alignment", False)):
            issues.extend(self._citation_support_alignment_issues(writing_text, upstream, policy))

        return issues

    @staticmethod
    def _has_citation_signal(text: str) -> bool:
        source_heading = re.search(r"(?im)^\s{0,3}#{1,6}\s*(sources?|references?|citations?|来源|参考)\b", text)
        citation_marker = re.search(r"(?:\[[0-9]{1,3}\]|\([A-Za-z][A-Za-z0-9 ._-]+,\s*\d{4}\))", text)
        return bool(source_heading or citation_marker)

    def _citation_audit(self, upstream: list[dict[str, Any]]) -> dict[str, Any]:
        writing_text = "\n".join(
            str(item.get("output") or "") for item in upstream if item.get("agent") == "writing"
        )
        attached_sources = [
            source
            for item in upstream
            for source in item.get("sources", [])
            if isinstance(source, dict)
        ]
        return {
            "cited_refs": self._extract_citation_refs(writing_text),
            "source_section_refs": self._extract_source_section_refs(writing_text),
            "attached_source_refs": self._extract_attached_source_refs(attached_sources),
            "attached_source_count": len(attached_sources),
        }

    @staticmethod
    def _extract_citation_refs(text: str) -> list[str]:
        refs: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"\[([0-9]{1,3})\]", text):
            ref = match.group(1).lstrip("0") or "0"
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
        return refs

    @staticmethod
    def _extract_source_section_refs(text: str) -> list[str]:
        refs: list[str] = []
        seen: set[str] = set()
        in_sources = False
        for line in text.splitlines():
            if ReviewAgent._is_source_heading(line):
                in_sources = True
                continue
            if in_sources and re.match(r"^\s{0,3}#{1,6}\s+", line):
                break
            if not in_sources:
                continue
            match = re.match(r"^\s*(?:[-*]\s*)?(?:\[?([0-9]{1,3})\]?)[\).:\s-]+", line)
            if match:
                ref = match.group(1).lstrip("0") or "0"
                if ref not in seen:
                    seen.add(ref)
                    refs.append(ref)
        return refs

    @staticmethod
    def _extract_attached_source_refs(sources: list[dict[str, Any]]) -> list[str]:
        refs: list[str] = []
        seen: set[str] = set()
        for source in sources:
            ref = ReviewAgent._attached_source_ref(source)
            if ref and ref not in seen:
                seen.add(ref)
                refs.append(ref)
        return refs

    def _citation_support_alignment_issues(
        self,
        writing_text: str,
        upstream: list[dict[str, Any]],
        policy: dict[str, Any],
    ) -> list[dict[str, str]]:
        source_text_by_ref = self._source_text_by_ref(writing_text, upstream)
        if not source_text_by_ref:
            return []

        issues: list[dict[str, str]] = []
        min_overlap = max(0.0, float(policy.get("citation_support_min_overlap", 0.12) or 0.12))
        for cited_ref, claim_window in self._extract_cited_claim_windows(writing_text):
            source_text = source_text_by_ref.get(cited_ref)
            if not source_text:
                continue
            overlap = self._token_overlap_ratio(claim_window, source_text)
            if overlap < min_overlap:
                issues.append(
                    self._issue(
                        "major",
                        "source",
                        f"Citation [{cited_ref}] does not appear to support the cited claim text.",
                        "Align the citation with a source that supports the claim, or revise the claim/source entry.",
                    )
                )
        return issues

    @staticmethod
    def _extract_cited_claim_windows(text: str) -> list[tuple[str, str]]:
        windows: list[tuple[str, str]] = []
        in_sources = False
        for line in text.splitlines():
            if ReviewAgent._is_source_heading(line):
                in_sources = True
                continue
            if in_sources and re.match(r"^\s{0,3}#{1,6}\s+", line):
                in_sources = False
            if in_sources:
                continue
            for match in re.finditer(r"\[([0-9]{1,3})\]", line):
                ref = match.group(1).lstrip("0") or "0"
                windows.append((ref, line.strip()))
        return windows

    def _source_text_by_ref(self, writing_text: str, upstream: list[dict[str, Any]]) -> dict[str, str]:
        source_texts = self._source_section_text_by_ref(writing_text)
        attached_sources = [
            source
            for item in upstream
            for source in item.get("sources", [])
            if isinstance(source, dict)
        ]
        for index, source in enumerate(attached_sources, start=1):
            ref = self._attached_source_ref(source) or str(index)
            parts = self._string_values(source)
            text = " ".join(part for part in parts if str(part).strip()).strip()
            if not ref or not text:
                continue
            source_texts[ref] = f"{source_texts.get(ref, '')} {text}".strip()
        return source_texts

    @staticmethod
    def _source_section_text_by_ref(text: str) -> dict[str, str]:
        source_texts: dict[str, str] = {}
        in_sources = False
        for line in text.splitlines():
            if ReviewAgent._is_source_heading(line):
                in_sources = True
                continue
            if in_sources and re.match(r"^\s{0,3}#{1,6}\s+", line):
                break
            if not in_sources:
                continue
            match = re.match(r"^\s*(?:[-*]\s*)?(?:\[?([0-9]{1,3})\]?)[\).:\s-]+(.+)$", line)
            if match:
                ref = match.group(1).lstrip("0") or "0"
                source_texts[ref] = match.group(2).strip()
        return source_texts

    @staticmethod
    def _attached_source_ref(source: dict[str, Any]) -> str:
        raw_ref = (
            source.get("citation_id")
            or source.get("ref")
            or source.get("reference")
            or source.get("id")
            or source.get("index")
        )
        match = re.search(r"[0-9]{1,3}", str(raw_ref or ""))
        return (match.group(0).lstrip("0") or "0") if match else ""

    @staticmethod
    def _is_source_heading(line: str) -> bool:
        return bool(re.match(r"(?i)^\s{0,3}#{1,6}\s*(sources?|references?|citations?|来源|参考)\b", line))

    @staticmethod
    def _token_overlap_ratio(left: str, right: str) -> float:
        left_tokens = ReviewAgent._content_tokens(left)
        right_tokens = ReviewAgent._content_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))

    @staticmethod
    def _content_tokens(text: str) -> set[str]:
        stop_words = {
            "and",
            "are",
            "for",
            "from",
            "has",
            "have",
            "that",
            "the",
            "this",
            "with",
        }
        return {
            token
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
            if token not in stop_words
        }

    @staticmethod
    def _citation_sort_key(value: str) -> tuple[int, str]:
        return (int(value), value) if value.isdigit() else (9999, value)

    def _evidence_text_for_traceability(self, upstream: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for item in upstream:
            if item.get("agent") != "writing":
                parts.append(str(item.get("output") or ""))
                parts.extend(self._string_values(item.get("artifacts")))
            parts.extend(self._string_values(item.get("sources")))
        return "\n".join(part for part in parts if part).lower()

    @staticmethod
    def _string_values(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            values: list[str] = []
            for nested in value.values():
                values.extend(ReviewAgent._string_values(nested))
            return values
        if isinstance(value, list):
            values = []
            for nested in value:
                values.extend(ReviewAgent._string_values(nested))
            return values
        if isinstance(value, (int, float)):
            return [str(value)]
        return []

    @staticmethod
    def _extract_numeric_date_tokens(text: str) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()
        for pattern in (r"\b\d{4}-\d{2}-\d{2}\b", r"\b\d+(?:\.\d+)?%?\b"):
            for match in re.finditer(pattern, text):
                token = match.group(0).lower()
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
        return tokens

    @staticmethod
    def _review_basis(request: str, upstream: list[dict[str, Any]]) -> list[str]:
        basis = [f"Request: {request or 'No review request provided.'}"]
        for item in upstream:
            agent = str(item.get("agent") or "agent")
            status = str(item.get("status") or "unknown")
            basis.append(f"{agent}: {status}")
        return basis

    @staticmethod
    def _issue(severity: str, category: str, message: str, fix: str) -> dict[str, str]:
        return {
            "severity": severity,
            "category": category,
            "message": message,
            "fix": fix,
        }

    @staticmethod
    def _check(item: str, status: str, details: str) -> dict[str, str]:
        return {
            "item": item,
            "status": status,
            "details": details,
        }


__all__ = ["ReviewAgent", "ReviewAgentConfig"]
