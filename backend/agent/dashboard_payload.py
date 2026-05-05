"""Dashboard payload normalization, rendering, and attachment parsing helpers."""

import json
import re
from typing import Any, Dict, Optional

from langchain_core.documents import Document

from backend.agent.dashboard_attachments import (
    _build_attachment_dashboard_fallback,
    _coerce_dashboard_cell_value,
    _extract_attachment_evidence,
    _extract_attachment_sections,
    _is_rate_like_metric,
    _looks_like_date_dimension,
    _parse_attachment_tables,
    _parse_numeric_dashboard_value,
)
from backend.agent.llm import _stringify_user_input

DASHBOARD_TRIGGER_KEYWORDS = (
    "仪表盘",
    "看板",
    "图表",
    "数据图",
    "可视化",
    "柱状图",
    "柱形图",
    "条形图",
    "折线图",
    "饼图",
    "趋势图",
    "统计图",
    "图形化",
    "dashboard",
)

DEFAULT_DASHBOARD_TEMPLATE: Dict[str, Any] = {
    "enabled": True,
    "title_hint": "知识库数据洞察",
    "focus_metrics": [],
    "preferred_charts": ["bar", "line", "pie"],
    "section_order": ["summary", "metrics", "charts", "table", "evidence", "warnings"],
    "audience_tone": "专业、直观、适合业务汇报",
}


def _extract_json_payload(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty response")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("json payload not found")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("json payload is not an object")
    return payload


def _normalize_dashboard_template(raw_template: Any) -> dict[str, Any]:
    template = dict(DEFAULT_DASHBOARD_TEMPLATE)
    if isinstance(raw_template, str) and raw_template.strip():
        try:
            raw_template = json.loads(raw_template)
        except json.JSONDecodeError:
            raw_template = {}
    if not isinstance(raw_template, dict):
        raw_template = {}

    template["enabled"] = raw_template.get("enabled") is not False

    title_hint = str(raw_template.get("title_hint", "")).strip()
    if title_hint:
        template["title_hint"] = title_hint

    focus_metrics = raw_template.get("focus_metrics", [])
    if isinstance(focus_metrics, list):
        template["focus_metrics"] = [str(item).strip() for item in focus_metrics if str(item).strip()]

    preferred_charts = raw_template.get("preferred_charts", [])
    if isinstance(preferred_charts, list):
        valid = [str(item).strip() for item in preferred_charts if str(item).strip() in {"bar", "line", "pie"}]
        if valid:
            template["preferred_charts"] = valid

    section_order = raw_template.get("section_order", [])
    if isinstance(section_order, list):
        valid_sections = [
            str(item).strip()
            for item in section_order
            if str(item).strip() in {"summary", "metrics", "charts", "table", "evidence", "warnings"}
        ]
        if valid_sections:
            template["section_order"] = valid_sections

    audience_tone = str(raw_template.get("audience_tone", "")).strip()
    if audience_tone:
        template["audience_tone"] = audience_tone

    return template


def _should_generate_dashboard(user_input: Any) -> bool:
    text = _stringify_user_input(user_input).lower()
    if any(keyword in text for keyword in DASHBOARD_TRIGGER_KEYWORDS):
        return True
    chart_pattern = re.compile(r"(柱状图|柱形图|条形图|折线图|饼图|趋势图|统计图|dashboard)")
    return bool(chart_pattern.search(text))


def _build_dashboard_sources(docs: list[Document]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for index, doc in enumerate(docs, start=1):
        snippet = re.sub(r"\s+", " ", doc.page_content).strip()[:240]
        title = str(doc.metadata.get("source", f"文档 {index}")).strip() or f"文档 {index}"
        evidence_id = f"e{index}"
        evidence.append(
            {
                "id": evidence_id,
                "title": title,
                "snippet": snippet,
                "source_type": "doc",
            }
        )
        sources.append(
            {
                "type": "doc",
                "title": title,
                "snippet": snippet,
                "index": index,
                "retrieval_mode": str(doc.metadata.get("retrieval_mode") or "").strip(),
                "search_channel": str(doc.metadata.get("search_channel") or "").strip(),
                "score": doc.metadata.get("search_score"),
                "matched_terms": doc.metadata.get("matched_terms") or [],
                "retrieval_query": str(doc.metadata.get("retrieval_query") or "").strip(),
                "feedback_boost": float(doc.metadata.get("feedback_boost", 0.0) or 0.0),
                "feedback_net": int(doc.metadata.get("feedback_net", 0) or 0),
                "feedback_positive_count": int(doc.metadata.get("feedback_positive_count", 0) or 0),
                "feedback_negative_count": int(doc.metadata.get("feedback_negative_count", 0) or 0),
                "version_label": str(doc.metadata.get("kb_version_label") or "").strip(),
                "lifecycle_status": str(doc.metadata.get("kb_lifecycle_status") or "").strip(),
                "is_latest": bool(doc.metadata.get("kb_is_latest", False)),
                "is_expired": bool(doc.metadata.get("kb_is_expired", False)),
            }
        )
    return evidence, sources


def _sanitize_dashboard_payload(
    payload: dict[str, Any],
    allowed_evidence: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    evidence_list = allowed_evidence if allowed_evidence is not None else payload.get("evidence", [])
    evidence_ids = {
        str(item.get("id")).strip()
        for item in evidence_list
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }

    sanitized_evidence = []
    for item in evidence_list:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("id", "")).strip()
        if not evidence_id:
            continue
        sanitized_evidence.append(
            {
                "id": evidence_id,
                "title": str(item.get("title", "未知来源")).strip() or "未知来源",
                "snippet": str(item.get("snippet", "")).strip(),
                "source_type": str(item.get("source_type", "doc")).strip() or "doc",
            }
        )

    metrics = []
    for metric in payload.get("metrics", []):
        if not isinstance(metric, dict):
            continue
        refs = [
            ref for ref in [str(item).strip() for item in metric.get("evidence_ids", []) if str(item).strip()]
            if ref in evidence_ids
        ]
        if not refs:
            continue
        metrics.append(
            {
                "label": str(metric.get("label", "")).strip() or "指标",
                "value": metric.get("value", ""),
                "unit": str(metric.get("unit", "")).strip(),
                "trend": str(metric.get("trend", "")).strip() or "flat",
                "delta": str(metric.get("delta", "")).strip(),
                "highlight": bool(metric.get("highlight", False)),
                "evidence_ids": refs,
            }
        )

    charts = []
    for chart in payload.get("charts", []):
        if not isinstance(chart, dict):
            continue
        refs = [
            ref for ref in [str(item).strip() for item in chart.get("evidence_ids", []) if str(item).strip()]
            if ref in evidence_ids
        ]
        chart_data = chart.get("chart_data")
        chart_type = str(chart.get("type", "")).strip()
        if chart_type not in {"bar", "line", "pie"}:
            continue
        if not refs or not isinstance(chart_data, dict):
            continue
        labels = [str(item) for item in chart_data.get("labels", [])]
        datasets = []
        for dataset in chart_data.get("datasets", []):
            if not isinstance(dataset, dict):
                continue
            data_values = dataset.get("data", [])
            if not isinstance(data_values, list):
                continue
            numeric_values = []
            valid = True
            for value in data_values:
                try:
                    numeric_values.append(float(value))
                except (TypeError, ValueError):
                    valid = False
                    break
            if not valid or len(numeric_values) != len(labels):
                continue
            datasets.append(
                {
                    "label": str(dataset.get("label", "")).strip() or "数据",
                    "data": numeric_values,
                }
            )
        if not labels or not datasets:
            continue
        charts.append(
            {
                "title": str(chart.get("title", "")).strip() or "图表",
                "type": chart_type,
                "description": str(chart.get("description", "")).strip(),
                "evidence_ids": refs,
                "chart_data": {
                    "type": chart_type,
                    "labels": labels,
                    "datasets": datasets,
                },
            }
        )

    table_payload = payload.get("table")
    table = None
    if isinstance(table_payload, dict):
        refs = [
            ref for ref in [str(item).strip() for item in table_payload.get("evidence_ids", []) if str(item).strip()]
            if ref in evidence_ids
        ]
        columns = [str(item).strip() for item in table_payload.get("columns", []) if str(item).strip()]
        rows = table_payload.get("rows", [])
        if refs and columns and isinstance(rows, list) and rows:
            safe_rows = []
            for row in rows:
                if isinstance(row, dict):
                    safe_rows.append({str(key): value for key, value in row.items() if str(key) in columns})
            if safe_rows:
                table = {
                    "title": str(table_payload.get("title", "")).strip() or "数据明细",
                    "columns": columns,
                    "rows": safe_rows,
                    "evidence_ids": refs,
                }

    warnings = [str(item).strip() for item in payload.get("warnings", []) if str(item).strip()]

    return {
        "title": str(payload.get("title", "")).strip() or "知识库仪表盘",
        "summary": str(payload.get("summary", "")).strip(),
        "metrics": metrics,
        "charts": charts,
        "table": table,
        "evidence": sanitized_evidence,
        "warnings": warnings,
    }


def _render_dashboard_card(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", "").strip()
    title = payload.get("title", "知识库仪表盘")
    intro = f"已根据当前角色绑定的知识库整理出可证据化的仪表盘：{title}"
    if summary:
        intro = f"{intro}\n\n{summary}"
    card_json = json.dumps(payload, ensure_ascii=False)
    return f"{intro}\n\n:::dashboard-card\n{card_json}\n:::"


def _render_attachment_dashboard_card(payload: dict[str, Any]) -> str:
    summary = str(payload.get("summary", "")).strip()
    title = str(payload.get("title", "")).strip() or "数据仪表盘"
    intro = f"已根据您上传的附件整理出仪表盘：{title}"
    if summary:
        intro = f"{intro}\n\n{summary}"
    card_json = json.dumps(payload, ensure_ascii=False)
    return f"{intro}\n\n:::dashboard-card\n{card_json}\n:::"


