"""Attachment parsing and fallback dashboard builders."""

import re
from typing import Any

from backend.agent.history import (
    CHAT_FILE_CONTEXT_END_MARKER,
    CHAT_FILE_CONTEXT_START_MARKER,
)
from backend.agent.llm import _stringify_user_input


def _extract_attachment_sections(user_input: Any) -> list[dict[str, Any]]:
    user_text = _stringify_user_input(user_input)
    pattern = (
        re.escape(CHAT_FILE_CONTEXT_START_MARKER)
        + r"(.*?)"
        + re.escape(CHAT_FILE_CONTEXT_END_MARKER)
    )
    blocks = re.findall(pattern, user_text, flags=re.DOTALL)
    if not blocks:
        return []

    sections: list[dict[str, Any]] = []
    attachment_counter = 0
    attachment_marker_re = re.compile(r"(?m)^\[附件\s*\d+\]\s*$")

    for block in blocks:
        matches = list(attachment_marker_re.finditer(block))
        if not matches:
            content = block.strip()
            if not content:
                continue
            attachment_counter += 1
            sections.append(
                {
                    "id": f"a{attachment_counter}",
                    "title": f"会话附件 {attachment_counter}",
                    "source": "会话附件",
                    "source_type": "attachment",
                    "snippet": content[:2000],
                    "content": content,
                }
            )
            continue

        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
            raw_section = block[start:end].strip()
            if not raw_section:
                continue

            lines = [line.strip() for line in raw_section.splitlines() if line.strip()]
            if not lines:
                continue

            file_name = f"会话附件 {attachment_counter + 1}"
            content_lines: list[str] = []
            for line in lines[1:]:
                if ("文件名" in line or line.lower().startswith("file")) and ("：" in line or ":" in line):
                    _, _, remainder = line.replace("：", ":", 1).partition(":")
                    candidate = remainder.strip()
                    if candidate:
                        file_name = candidate
                    continue
                normalized_line = line.replace("：", ":")
                if normalized_line in {"内容:", "正文:", "content:"}:
                    continue
                content_lines.append(line)

            content = "\n".join(content_lines).strip()
            if not content:
                continue

            attachment_counter += 1
            sections.append(
                {
                    "id": f"a{attachment_counter}",
                    "title": file_name,
                    "source": "会话附件",
                    "source_type": "attachment",
                    "snippet": content[:2000],
                    "content": content,
                }
            )

    return sections


def _extract_attachment_evidence(user_input: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": section["id"],
            "title": section["title"],
            "source": section["source"],
            "source_type": section["source_type"],
            "snippet": section["snippet"],
        }
        for section in _extract_attachment_sections(user_input)
    ]


def _parse_numeric_dashboard_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value or "").strip()
    if not text:
        return None

    normalized = text.replace(",", "")
    if normalized.endswith("%"):
        normalized = normalized[:-1].strip()

    if not re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
        return None

    return float(normalized)


def _coerce_dashboard_cell_value(value: str) -> Any:
    numeric_value = _parse_numeric_dashboard_value(value)
    if numeric_value is None:
        return value.strip()
    if numeric_value.is_integer():
        return int(numeric_value)
    return round(numeric_value, 6)


def _is_rate_like_metric(label: str) -> bool:
    lowered = (label or "").strip().lower()
    return any(
        token in lowered
        for token in ("率", "ratio", "ctr", "cvr", "roi", "转化", "占比")
    )


def _looks_like_date_dimension(label: str, sample_values: list[str]) -> bool:
    lowered = (label or "").strip().lower()
    if any(token in lowered for token in ("date", "日期", "时间", "月份", "month", "day", "周", "week")):
        return True
    return any(re.search(r"\d{4}[-/]\d{1,2}([-/]\d{1,2})?", value) for value in sample_values[:3])


def _parse_attachment_tables(text: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    current_table: dict[str, Any] | None = None

    def ensure_table(sheet_name: str | None) -> dict[str, Any]:
        nonlocal current_table
        normalized_name = (sheet_name or "").strip()
        if current_table is not None and current_table["sheet_name"] == normalized_name:
            return current_table
        current_table = {
            "sheet_name": normalized_name,
            "columns": [],
            "rows": [],
        }
        tables.append(current_table)
        return current_table

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        sheet_match = re.match(r"^[【\[]?\s*Sheet\s*[:：]\s*(.+?)\s*[】\]]?$", line, flags=re.IGNORECASE)
        if sheet_match:
            ensure_table(sheet_match.group(1).strip())
            continue

        row_match = re.match(r"^行\s*\d+\s*[:：]\s*(.+)$", line)
        row_text = row_match.group(1).strip() if row_match else ""
        if not row_text and "|" in line and ("：" in line or ":" in line):
            row_text = line
        if not row_text:
            continue

        row: dict[str, Any] = {}
        for cell in [item.strip() for item in row_text.split("|") if item.strip()]:
            if "：" in cell:
                key, value = cell.split("：", 1)
            elif ":" in cell:
                key, value = cell.split(":", 1)
            else:
                continue
            key = key.strip()
            value = value.strip()
            if not key or not value:
                continue
            row[key] = _coerce_dashboard_cell_value(value)

        if not row:
            continue

        table = current_table or ensure_table("")
        for column in row:
            if column not in table["columns"]:
                table["columns"].append(column)
        table["rows"].append(row)

    return [table for table in tables if table["rows"]]


def _build_attachment_dashboard_fallback(
    attachment_sections: list[dict[str, Any]],
    template: dict[str, Any],
) -> dict[str, Any] | None:
    parsed_candidates: list[dict[str, Any]] = []
    for section in attachment_sections:
        for table in _parse_attachment_tables(section.get("content", "")):
            parsed_candidates.append({"section": section, "table": table})

    if not parsed_candidates:
        return None

    def candidate_score(candidate: dict[str, Any]) -> tuple[int, int]:
        table = candidate["table"]
        rows = table.get("rows", [])
        numeric_columns = 0
        for column in table.get("columns", []):
            values = [
                _parse_numeric_dashboard_value(row.get(column))
                for row in rows
                if row.get(column) not in (None, "")
            ]
            if values and all(value is not None for value in values):
                numeric_columns += 1
        return (len(rows), numeric_columns)

    best_candidate = max(parsed_candidates, key=candidate_score)
    section = best_candidate["section"]
    table = best_candidate["table"]
    columns = list(table.get("columns", []))
    rows = list(table.get("rows", []))

    numeric_columns: list[tuple[str, list[float]]] = []
    dimension_candidates: list[tuple[str, list[str]]] = []
    for column in columns:
        raw_values = [row.get(column) for row in rows if row.get(column) not in (None, "")]
        if not raw_values:
            continue
        numeric_values = [_parse_numeric_dashboard_value(value) for value in raw_values]
        if all(value is not None for value in numeric_values):
            numeric_columns.append((column, [float(value) for value in numeric_values if value is not None]))
            continue
        dimension_candidates.append((column, [str(value) for value in raw_values]))

    if not numeric_columns and not rows:
        return None

    preferred_metric_tokens = (
        "销售额", "营收", "收入", "金额", "gmv",
        "订单", "销量", "访问", "流量", "用户", "客户", "转化", "率",
    )

    def metric_sort_key(item: tuple[str, list[float]]) -> tuple[int, int, str]:
        label = item[0]
        lowered = label.lower()
        preferred_rank = 0
        for index, token in enumerate(preferred_metric_tokens):
            if token in lowered:
                preferred_rank = len(preferred_metric_tokens) - index
                break
        return (preferred_rank, len(item[1]), label)

    numeric_columns.sort(key=metric_sort_key, reverse=True)

    preferred_dimension_tokens = (
        "日期", "时间", "月份", "date", "month",
        "区域", "地区", "城市", "省份",
        "产品", "品类", "类别", "渠道", "部门",
    )

    def dimension_sort_key(item: tuple[str, list[str]]) -> tuple[int, int, str]:
        label = item[0]
        lowered = label.lower()
        preferred_rank = 0
        for index, token in enumerate(preferred_dimension_tokens):
            if token in lowered:
                preferred_rank = len(preferred_dimension_tokens) - index
                break
        return (preferred_rank, len(item[1]), label)

    dimension_candidates.sort(key=dimension_sort_key, reverse=True)

    metrics: list[dict[str, Any]] = []
    for index, (label, values) in enumerate(numeric_columns[:3]):
        if not values:
            continue
        if _is_rate_like_metric(label):
            aggregate_value = sum(values) / len(values)
            if 0 <= aggregate_value <= 1:
                metric_value: str | int | float = round(aggregate_value * 100, 2)
            else:
                metric_value = round(aggregate_value, 2)
            unit = "%"
        else:
            aggregate_value = sum(values)
            metric_value = int(aggregate_value) if aggregate_value.is_integer() else round(aggregate_value, 2)
            unit = ""
        metrics.append(
            {
                "label": label,
                "value": metric_value,
                "unit": unit,
                "trend": "flat",
                "delta": "",
                "highlight": index == 0,
                "evidence_ids": [section["id"]],
            }
        )

    charts: list[dict[str, Any]] = []
    if numeric_columns:
        dimension_label = dimension_candidates[0][0] if dimension_candidates else ""
        metric_label = numeric_columns[0][0]
        chart_rows = []
        for row in rows:
            raw_metric = row.get(metric_label)
            metric_value = _parse_numeric_dashboard_value(raw_metric)
            if metric_value is None:
                continue
            if dimension_label:
                raw_dimension = row.get(dimension_label)
                if raw_dimension in (None, ""):
                    continue
                label_value = str(raw_dimension)
            else:
                label_value = f"第{len(chart_rows) + 1}行"
            chart_rows.append((label_value, float(metric_value)))
            if len(chart_rows) >= 8:
                break

        if len(chart_rows) >= 2:
            preferred_charts = template.get("preferred_charts", [])
            chart_type = "line" if dimension_label and _looks_like_date_dimension(
                dimension_label,
                [label for label, _ in chart_rows],
            ) else "bar"
            if chart_type not in {"bar", "line", "pie"}:
                chart_type = "bar"
            if preferred_charts and chart_type not in preferred_charts:
                preferred_chart = preferred_charts[0]
                if preferred_chart in {"bar", "line", "pie"}:
                    chart_type = preferred_chart

            charts.append(
                {
                    "title": f"{metric_label}趋势" if chart_type == "line" else f"{metric_label}对比",
                    "type": chart_type,
                    "description": (
                        f"按{dimension_label}展示{metric_label}"
                        if dimension_label
                        else f"展示{metric_label}的前 {len(chart_rows)} 条记录"
                    ),
                    "evidence_ids": [section["id"]],
                    "chart_data": {
                        "type": chart_type,
                        "labels": [label for label, _ in chart_rows],
                        "datasets": [
                            {
                                "label": metric_label,
                                "data": [value for _, value in chart_rows],
                            }
                        ],
                    },
                }
            )

    table_rows = [
        {column: row.get(column, "") for column in columns}
        for row in rows[:12]
    ]
    evidence = [
        {
            "id": item["id"],
            "title": item["title"],
            "snippet": item["snippet"],
            "source_type": item.get("source_type", "attachment"),
        }
        for item in attachment_sections
    ]

    title_hint = str(template.get("title_hint", "")).strip()
    sheet_name = str(table.get("sheet_name", "")).strip()
    attachment_title = str(section.get("title", "会话附件")).strip() or "会话附件"
    card_title = title_hint or (f"{sheet_name}数据看板" if sheet_name else f"{attachment_title}数据看板")

    summary_parts = [f"已从 {attachment_title} 中识别出 {len(rows)} 条记录"]
    if sheet_name:
        summary_parts.append(f"当前展示工作表“{sheet_name}”")
    if metrics:
        summary_parts.append(f"提炼出 {len(metrics)} 个核心指标")
    elif numeric_columns:
        summary_parts.append("已提取数值列，可继续细化成更明确的业务指标")
    else:
        summary_parts.append("当前以明细表形式展示，适合继续指定维度和指标")

    warnings: list[str] = []
    if len(rows) > len(table_rows):
        warnings.append(f"为便于展示，仅展示前 {len(table_rows)} 条明细记录。")
    if len(parsed_candidates) > 1:
        warnings.append("检测到多个附件或工作表，当前优先展示记录数最多的一组数据。")
    if not charts:
        warnings.append("已保留数据明细，但当前自动图表维度不够稳定，建议进一步指定维度和指标。")

    return {
        "title": card_title,
        "summary": "；".join(summary_parts) + "。",
        "metrics": metrics,
        "charts": charts,
        "table": {
            "title": sheet_name or "数据明细",
            "columns": columns,
            "rows": table_rows,
            "evidence_ids": [section["id"]],
        } if columns and table_rows else None,
        "evidence": evidence,
        "warnings": warnings,
    }
