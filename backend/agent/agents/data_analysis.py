"""Data Analysis Agent for profiling tabular workflow inputs."""

from __future__ import annotations

import asyncio
import csv
import json
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from statistics import mean
from typing import Any

from backend.agent.protocols import AgentResult, AgentTask


@dataclass(slots=True)
class DataAnalysisAgentConfig:
    timeout_seconds: float = 90.0
    max_rows: int = 500
    max_file_bytes: int = 5 * 1024 * 1024
    max_context_chars: int = 8000
    supported_file_extensions: tuple[str, ...] = (".csv", ".tsv", ".json", ".xlsx", ".xls")
    default_query_limit: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)


class DataAnalysisAgent:
    """Profiles tabular input and produces compact analysis artifacts."""

    name = "data_analysis"
    description = "Data Agent for tabular analysis, summaries, and chart-ready profiles."
    capabilities = ["data_analysis", "data", "dashboard", "csv", "excel", "statistics"]

    def __init__(
        self,
        *,
        llm: Any | None = None,
        config: DataAnalysisAgentConfig | None = None,
    ) -> None:
        self.llm = llm
        self.config = config or DataAnalysisAgentConfig()

    def can_handle(self, task_type: str) -> bool:
        normalized = str(task_type or "").strip().lower()
        return normalized in {capability.lower() for capability in self.capabilities}

    async def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        request = self._request_text(task)
        rows, source_label = self._extract_rows(task, context)
        profile = self._profile_rows(rows)
        sampling = self._extract_sampling_config(task, context)
        if isinstance(sampling, dict):
            profile["sampling"] = sampling
        query_result: dict[str, Any] | None = None
        query_config = self._extract_query_config(task, context)

        if not rows:
            output = self._fallback_output(request, context)
            artifacts: list[dict[str, Any]] = []
        else:
            output = self._render_profile(profile, source_label)
            query_result = self._query_rows(request, rows, profile, query_config=query_config)
            if query_result:
                output = f"{output}\n\n{self._render_query_result(query_result)}"
            chart_spec = self._build_chart_spec(profile, query_result=query_result)
            dashboard_payload = self._build_dashboard_payload(
                profile,
                chart_spec=chart_spec,
                query_result=query_result,
                source_label=source_label,
            )
            if self.llm is not None:
                output = await self._summarize_with_llm(request, profile, output)
            if dashboard_payload:
                output = f"{output}\n\n{self._render_dashboard_block(dashboard_payload)}"
            artifacts = [
                {
                    "type": "json",
                    "title": "Data profile",
                    "content": profile,
                }
            ]
            if query_result:
                artifacts.append(
                    {
                        "type": "query_result",
                        "title": "Query result",
                        "content": query_result,
                    }
                )
            if chart_spec:
                artifacts.append(
                    {
                        "type": "chart_spec",
                        "title": "Suggested chart",
                        "content": chart_spec,
                    }
                )
            if dashboard_payload:
                artifacts.append(
                    {
                        "type": "dashboard_card",
                        "title": "Dashboard card",
                        "content": dashboard_payload,
                    }
                )

        return {
            "agent": self.name,
            "task_id": str(task.get("id") or ""),
            "task_type": str(task.get("type") or ""),
            "status": "completed",
            "output": output,
            "artifacts": artifacts,
            "sources": self._sources(source_label, rows),
            "metadata": {
                **self.config.metadata,
                "context_keys": sorted(context.keys()),
                "used_llm": self.llm is not None and bool(rows),
                "row_count": len(rows),
                "source": source_label,
                "sampling": sampling if isinstance(sampling, dict) else {},
                "query_applied": bool(query_result),
                "query_config_source": query_config.get("_source", "") if query_config else "",
                "applied_filter_tree": query_result.get("filter_tree") if query_result else None,
            },
        }

    @staticmethod
    def _request_text(task: AgentTask) -> str:
        raw_input = task.get("input")
        if isinstance(raw_input, str) and raw_input.strip():
            return raw_input.strip()
        if isinstance(raw_input, dict):
            for key in ("query", "request", "question", "prompt"):
                value = raw_input.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return str(task.get("description") or "").strip()

    def _extract_rows(
        self,
        task: AgentTask,
        context: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], str]:
        task_metadata = task.get("metadata") or {}
        candidates = [
            (task.get("input"), "task.input"),
            (task_metadata.get("rows"), "task.metadata.rows"),
            (task_metadata.get("file_path"), "task.metadata.file_path"),
            (task_metadata.get("path"), "task.metadata.path"),
            (task_metadata.get("dataset_path"), "task.metadata.dataset_path"),
            (context.get("rows"), "context.rows"),
            (context.get("data"), "context.data"),
            (context.get("file_path"), "context.file_path"),
            (context.get("dataset_path"), "context.dataset_path"),
        ]
        for value, label in candidates:
            rows = self._coerce_rows(value)
            if rows:
                return rows[: max(1, int(self.config.max_rows))], label
        return [], ""

    @staticmethod
    def _extract_query_config(task: AgentTask, context: dict[str, Any]) -> dict[str, Any]:
        task_metadata = task.get("metadata") or {}
        candidates = (
            (task_metadata.get("query"), "task.metadata.query"),
            (context.get("data_query"), "context.data_query"),
        )
        for value, source in candidates:
            if isinstance(value, dict):
                return {**value, "_source": source}
        return {}

    @staticmethod
    def _extract_sampling_config(task: AgentTask, context: dict[str, Any]) -> dict[str, Any]:
        task_metadata = task.get("metadata") or {}
        for value in (
            task_metadata.get("sampling"),
            context.get("data_sampling_config"),
            context.get("data_sampling"),
        ):
            if isinstance(value, dict):
                return dict(value)
        return {}

    def _coerce_rows(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return self._rows_from_list(value)
        if isinstance(value, dict):
            for key in ("rows", "records", "data"):
                rows = self._coerce_rows(value.get(key))
                if rows:
                    return rows
            for key in ("file_path", "path", "dataset_path"):
                rows = self._rows_from_file_path(value.get(key))
                if rows:
                    return rows
        if isinstance(value, str) and value.strip():
            text = value.strip()
            rows = self._rows_from_file_path(text)
            if rows:
                return rows
            rows = self._rows_from_json(text)
            if rows:
                return rows
            return self._rows_from_csv(text)
        return []

    @staticmethod
    def _rows_from_list(value: list[Any]) -> list[dict[str, Any]]:
        if not value:
            return []
        if all(isinstance(item, dict) for item in value):
            return [{str(key): cell for key, cell in item.items()} for item in value]
        if all(isinstance(item, list) for item in value) and value:
            headers = [str(item) for item in value[0]]
            rows: list[dict[str, Any]] = []
            for raw_row in value[1:]:
                rows.append({headers[index]: cell for index, cell in enumerate(raw_row[: len(headers)])})
            return rows
        return []

    def _rows_from_json(self, text: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return []
        return self._coerce_rows(payload)

    def _rows_from_file_path(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, (str, Path)):
            return []
        raw_path = str(value).strip()
        if not raw_path:
            return []

        path = Path(raw_path).expanduser()
        try:
            if not path.is_file():
                return []
            suffix = path.suffix.lower()
            if suffix not in self.config.supported_file_extensions:
                return []
            if path.stat().st_size > max(1, int(self.config.max_file_bytes)):
                return []
        except OSError:
            return []

        if suffix in {".csv", ".tsv"}:
            delimiter = "\t" if suffix == ".tsv" else None
            text = self._read_text_file(path)
            return self._rows_from_csv(text, delimiter=delimiter)
        if suffix == ".json":
            return self._rows_from_json(self._read_text_file(path))
        if suffix in {".xlsx", ".xls"}:
            return self._rows_from_excel(path)
        return []

    @staticmethod
    def _read_text_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _rows_from_csv(text: str, *, delimiter: str | None = None) -> list[dict[str, Any]]:
        if delimiter is None and "," not in text and "\t" not in text and ";" not in text:
            return []
        sample = text[:2048]
        if delimiter is not None:
            dialect = csv.excel_tab if delimiter == "\t" else csv.excel
        else:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            except csv.Error:
                dialect = csv.excel
        reader = csv.DictReader(StringIO(text), dialect=dialect)
        return [{str(key): value for key, value in row.items() if key is not None} for row in reader]

    def _rows_from_excel(self, path: Path) -> list[dict[str, Any]]:
        try:
            import pandas as pd
        except ImportError:
            return []
        try:
            frame = pd.read_excel(path, nrows=max(1, int(self.config.max_rows)))
        except Exception:
            return []
        frame = frame.where(pd.notnull(frame), None)
        rows = frame.to_dict(orient="records")
        return [{str(key): value for key, value in row.items()} for row in rows]

    def _profile_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        columns = list(dict.fromkeys(key for row in rows for key in row.keys()))
        numeric_columns: dict[str, dict[str, Any]] = {}
        categorical_columns: dict[str, dict[str, Any]] = {}
        missing_by_column: dict[str, int] = {}

        for column in columns:
            values = [row.get(column) for row in rows]
            missing_by_column[column] = sum(1 for value in values if self._is_missing(value))
            numeric_values = [
                parsed
                for parsed in (self._parse_number(value) for value in values)
                if parsed is not None
            ]
            if numeric_values and len(numeric_values) >= max(1, len(rows) // 2):
                numeric_columns[column] = {
                    "count": len(numeric_values),
                    "sum": round(sum(numeric_values), 6),
                    "mean": round(mean(numeric_values), 6),
                    "min": round(min(numeric_values), 6),
                    "max": round(max(numeric_values), 6),
                }
                continue

            counts: dict[str, int] = {}
            for value in values:
                if self._is_missing(value):
                    continue
                key = str(value).strip()
                counts[key] = counts.get(key, 0) + 1
            if counts:
                categorical_columns[column] = {
                    "unique": len(counts),
                    "top_values": [
                        {"value": key, "count": count}
                        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
                    ],
                }

        return {
            "row_count": len(rows),
            "column_count": len(columns),
            "columns": columns,
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "missing_by_column": missing_by_column,
            "preview_rows": rows[:5],
        }

    @staticmethod
    def _is_missing(value: Any) -> bool:
        return value is None or str(value).strip() == ""

    @staticmethod
    def _parse_number(value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _render_profile(profile: dict[str, Any], source_label: str) -> str:
        numeric_columns = profile.get("numeric_columns", {})
        categorical_columns = profile.get("categorical_columns", {})
        lines = [
            "Data Agent Analysis",
            "",
            f"- Source: {source_label}",
            f"- Rows: {profile.get('row_count', 0)}",
            f"- Columns: {profile.get('column_count', 0)}",
        ]
        sampling = profile.get("sampling")
        if isinstance(sampling, dict) and sampling.get("sampled"):
            lines.append(
                "- Sampling: showing "
                f"{sampling.get('sampled_row_count', profile.get('row_count', 0))} "
                f"of {sampling.get('row_count', profile.get('row_count', 0))} parsed rows"
            )
        if numeric_columns:
            lines.append("- Numeric fields:")
            for column, stats in list(numeric_columns.items())[:5]:
                lines.append(
                    f"  - {column}: sum={stats['sum']}, mean={stats['mean']}, "
                    f"min={stats['min']}, max={stats['max']}"
                )
        if categorical_columns:
            lines.append("- Categorical fields:")
            for column, stats in list(categorical_columns.items())[:5]:
                top_values = ", ".join(
                    f"{item['value']}({item['count']})" for item in stats.get("top_values", [])[:3]
                )
                lines.append(f"  - {column}: unique={stats['unique']}, top={top_values}")
        return "\n".join(lines)

    @staticmethod
    def _build_chart_spec(
        profile: dict[str, Any],
        *,
        query_result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if query_result and query_result.get("operation") in {"grouped_rank", "grouped_summary"}:
            labels = [str(row.get("dimension", "")) for row in query_result.get("rows", [])]
            data = [
                DataAnalysisAgent._parse_number(row.get("value"))
                for row in query_result.get("rows", [])
            ]
            numeric_data = [value for value in data if value is not None]
            if labels and len(labels) == len(numeric_data):
                metric = str(query_result.get("metric") or "value")
                dimension = str(query_result.get("dimension") or "dimension")
                return {
                    "type": DataAnalysisAgent._infer_chart_type(dimension, labels, operation=str(query_result.get("operation") or "")),
                    "labels": labels,
                    "datasets": [{"label": metric, "data": numeric_data}],
                    "dimension": dimension,
                    "metric": metric,
                    "aggregation": query_result.get("aggregation", "sum"),
                }

        numeric_columns = profile.get("numeric_columns", {})
        categorical_columns = profile.get("categorical_columns", {})
        if not numeric_columns or not categorical_columns:
            return None
        dimension = next(iter(categorical_columns))
        metric = next(iter(numeric_columns))
        rows = profile.get("preview_rows", [])
        labels = [str(row.get(dimension, "")) for row in rows if str(row.get(dimension, "")).strip()]
        data = [
            DataAnalysisAgent._parse_number(row.get(metric))
            for row in rows
            if str(row.get(dimension, "")).strip()
        ]
        numeric_data = [value for value in data if value is not None]
        if not labels or len(labels) != len(numeric_data):
            return None
        return {
            "type": DataAnalysisAgent._infer_chart_type(dimension, labels),
            "labels": labels,
            "datasets": [{"label": metric, "data": numeric_data}],
            "dimension": dimension,
            "metric": metric,
        }

    @staticmethod
    def _infer_chart_type(
        dimension: str,
        labels: list[str],
        *,
        operation: str = "",
    ) -> str:
        normalized_dimension = str(dimension or "").strip().lower()
        time_tokens = ("date", "time", "month", "year", "day", "week", "日期", "时间", "月份", "年度", "年份")
        if any(token in normalized_dimension for token in time_tokens):
            return "line"
        if labels and len(labels) >= 3 and all(DataAnalysisAgent._looks_time_like_label(label) for label in labels[:8]):
            return "line"
        if operation == "grouped_summary" and 2 <= len(labels) <= 6:
            return "pie"
        return "bar"

    @staticmethod
    def _looks_time_like_label(label: str) -> bool:
        text = str(label or "").strip()
        if not text:
            return False
        return bool(
            re.match(r"^\d{4}([-/]\d{1,2})?([-/]\d{1,2})?$", text)
            or re.match(r"^\d{1,2}[/.-]\d{1,2}([/.-]\d{2,4})?$", text)
            or re.match(r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", text, flags=re.IGNORECASE)
        )

    def _query_rows(
        self,
        request: str,
        rows: list[dict[str, Any]],
        profile: dict[str, Any],
        *,
        query_config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        query_config = query_config or {}
        query_text = str(query_config.get("request") or query_config.get("query") or request or "")
        intent = str(query_config.get("intent") or self._infer_query_intent(query_text)).strip().lower()
        has_structured_query = any(
            key in query_config
            for key in (
                "metric",
                "dimension",
                "aggregation",
                "limit",
                "filters",
                "filter_groups",
                "filter_tree",
            )
        )
        if intent == "none" and has_structured_query:
            intent = "aggregate" if query_config.get("dimension") else "top"
        if intent == "none":
            return None

        filter_tree = self._query_filter_tree(query_config, query_text, profile)
        filter_groups = self._filter_tree_to_filter_groups(filter_tree)
        filters = [item for group in filter_groups for item in group]
        filtered_rows = self._apply_filter_tree(rows, filter_tree)
        if filter_tree and not filtered_rows:
            return {
                "intent": intent,
                "operation": "filtered_empty",
                "metric": "",
                "dimension": "",
                "limit": self._query_limit(query_config, query_text),
                "filters": filters,
                "filter_groups": filter_groups,
                "filter_tree": filter_tree,
                "rows": [],
            }
        working_rows = filtered_rows if filter_tree else rows

        aggregation = str(query_config.get("aggregation") or self._select_aggregation(query_text)).strip().lower()
        metric = str(query_config.get("metric") or self._select_metric(query_text, profile)).strip()
        if aggregation == "count":
            metric = "count"
        if not metric and aggregation != "count":
            return None
        dimension = str(query_config.get("dimension") or self._select_dimension(query_text, profile)).strip()
        limit = self._query_limit(query_config, query_text)

        if dimension:
            grouped = self._aggregate_by_dimension(working_rows, dimension, metric, aggregation=aggregation)
            if grouped:
                if intent == "aggregate":
                    sorted_groups = sorted(grouped, key=lambda item: self._dimension_sort_key(item.get("dimension")))
                else:
                    sorted_groups = sorted(
                        grouped,
                        key=lambda item: item["value"],
                        reverse=intent != "bottom",
                    )
                ranked_groups = sorted_groups[:limit]
                return {
                    "intent": intent,
                    "operation": "grouped_summary" if intent == "aggregate" else "grouped_rank",
                    "metric": metric,
                    "dimension": dimension,
                    "aggregation": aggregation,
                    "limit": limit,
                    "filters": filters,
                    "filter_groups": filter_groups,
                    "filter_tree": filter_tree,
                    "rows": ranked_groups,
                }

        ranked_rows = sorted(
            [
                {**row, metric: parsed}
                for row in working_rows
                if (parsed := self._parse_number(row.get(metric))) is not None
            ],
            key=lambda row: row[metric],
            reverse=intent != "bottom",
        )[:limit]
        if not ranked_rows:
            return None
        return {
            "intent": intent,
            "operation": "row_rank",
            "metric": metric,
            "dimension": "",
            "aggregation": aggregation,
            "limit": limit,
            "filters": filters,
            "filter_groups": filter_groups,
            "filter_tree": filter_tree,
            "rows": ranked_rows,
        }

    def _query_limit(self, query_config: dict[str, Any], request: str) -> int:
        raw_limit = query_config.get("limit")
        if raw_limit is None:
            raw_limit = query_config.get("sample_limit")
        if raw_limit is None:
            return self._extract_query_limit(request)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return self._extract_query_limit(request)
        return max(1, min(limit, int(self.config.max_rows)))

    def _query_filter_tree(
        self,
        query_config: dict[str, Any],
        request: str,
        profile: dict[str, Any],
    ) -> dict[str, Any] | None:
        if "filter_tree" in query_config:
            return self._normalize_filter_tree(query_config.get("filter_tree"))
        if "filter_groups" in query_config:
            return self._filter_groups_to_tree(query_config.get("filter_groups"))
        if "filters" in query_config:
            return self._filters_to_tree(query_config.get("filters"))

        filter_groups = self._extract_filter_groups(request, profile)
        return self._filter_groups_to_tree(filter_groups)

    @staticmethod
    def _legacy_infer_query_intent(request: str) -> str:
        text = str(request or "").strip().lower()
        if not text:
            return "none"
        if any(token in text for token in ("最低", "最少", "bottom", "lowest", "least", "min")):
            return "bottom"
        if any(token in text for token in ("最高", "最多", "最大", "前", "top", "highest", "most", "max")):
            return "top"
        return "none"

    @staticmethod
    def _select_metric(request: str, profile: dict[str, Any]) -> str:
        numeric_columns = list((profile.get("numeric_columns") or {}).keys())
        return DataAnalysisAgent._select_named_column(request, numeric_columns) or (numeric_columns[0] if numeric_columns else "")

    @staticmethod
    def _select_dimension(request: str, profile: dict[str, Any]) -> str:
        categorical_columns = list((profile.get("categorical_columns") or {}).keys())
        return DataAnalysisAgent._select_named_column(request, categorical_columns) or (
            categorical_columns[0] if categorical_columns else ""
        )

    @staticmethod
    def _select_named_column(request: str, columns: list[str]) -> str:
        normalized_request = str(request or "").lower()
        for column in columns:
            if str(column).lower() in normalized_request:
                return column
        return ""

    @staticmethod
    def _dimension_sort_key(value: Any) -> tuple[int, float | str]:
        text = str(value or "").strip()
        if not text:
            return (2, "")
        normalized = text.replace("/", "-")
        match = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$", normalized)
        if match:
            year = int(match.group(1))
            month = int(match.group(2) or 1)
            day = int(match.group(3) or 1)
            return (0, year * 10000 + month * 100 + day)
        numeric = DataAnalysisAgent._parse_number(text)
        if numeric is not None:
            return (0, numeric)
        return (1, text.lower())

    @staticmethod
    def _select_aggregation(request: str) -> str:
        text = str(request or "").strip().lower()
        if any(token in text for token in ("average", "avg", "mean", "\u5e73\u5747", "\u5747\u503c")):
            return "avg"
        if any(token in text for token in ("count", "number of", "\u8ba1\u6570", "\u6570\u91cf", "\u591a\u5c11")):
            return "count"
        return "sum"

    def _extract_filters(self, request: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
        text = str(request or "")
        if not text.strip():
            return []

        columns = [str(column) for column in profile.get("columns", [])]
        filters: list[dict[str, Any]] = []
        for column in columns:
            escaped = re.escape(column)
            patterns = [
                rf"\b{escaped}\b\s*(>=|<=|!=|=|>|<)\s*['\"]?([^,'\"\n;]+)",
                rf"\b{escaped}\b\s+(?:is|equals?|contains|like|为|是|等于|包含)\s+['\"]?([^,'\"\n;]+)",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    if len(match.groups()) == 2:
                        operator = match.group(1)
                        value = match.group(2)
                    else:
                        raw_operator = match.group(0).lower()
                        operator = "contains" if "contains" in raw_operator or "like" in raw_operator or "包含" in raw_operator else "="
                        value = match.group(1)
                    value = self._clean_filter_value(value)
                    if value:
                        filters.append({"column": column, "operator": operator, "value": value})

            numeric_patterns = [
                (rf"\b{escaped}\b\s+(?:greater than|above|over|大于|超过)\s*(-?\d+(?:\.\d+)?)", ">"),
                (rf"\b{escaped}\b\s+(?:less than|below|under|小于|低于)\s*(-?\d+(?:\.\d+)?)", "<"),
                (rf"\b{escaped}\b\s+(?:at least|不少于|大于等于)\s*(-?\d+(?:\.\d+)?)", ">="),
                (rf"\b{escaped}\b\s+(?:at most|不超过|小于等于)\s*(-?\d+(?:\.\d+)?)", "<="),
            ]
            for pattern, operator in numeric_patterns:
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    value = self._clean_filter_value(match.group(1))
                    if value:
                        filters.append({"column": column, "operator": operator, "value": value})

        unique_filters: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in filters:
            key = (str(item["column"]), str(item["operator"]), str(item["value"]).lower())
            if key in seen:
                continue
            seen.add(key)
            unique_filters.append(item)
        return unique_filters

    @staticmethod
    def _clean_filter_value(value: Any) -> str:
        text = str(value or "").strip().strip("'\"` ")
        return re.split(r"\s+(?:and|or|by|group\s+by|按|并且|或者)\s+", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    def _apply_filters(
        self,
        rows: list[dict[str, Any]],
        filters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not filters:
            return rows
        return [row for row in rows if all(self._row_matches_filter(row, item) for item in filters)]

    def _row_matches_filter(self, row: dict[str, Any], filter_item: dict[str, Any]) -> bool:
        column = str(filter_item.get("column") or "")
        operator = str(filter_item.get("operator") or "=").lower()
        expected = str(filter_item.get("value") or "").strip()
        actual = row.get(column)
        actual_number = self._parse_number(actual)
        expected_number = self._parse_number(expected)

        if operator in {">", ">=", "<", "<="}:
            if actual_number is None or expected_number is None:
                return False
            if operator == ">":
                return actual_number > expected_number
            if operator == ">=":
                return actual_number >= expected_number
            if operator == "<":
                return actual_number < expected_number
            return actual_number <= expected_number

        actual_text = str(actual or "").strip().lower()
        expected_text = expected.lower()
        if operator in {"!=", "<>"}:
            return actual_text != expected_text
        if operator == "contains":
            return expected_text in actual_text
        return actual_text == expected_text

    def _legacy_extract_query_limit(self, request: str) -> int:
        text = str(request or "")
        match = re.search(r"(?:top|前|末尾|bottom)\s*(\d{1,3})", text, flags=re.IGNORECASE)
        if not match:
            match = re.search(r"(\d{1,3})\s*(?:个|条|rows?|records?)", text, flags=re.IGNORECASE)
        if not match:
            return max(1, int(self.config.default_query_limit))
        return max(1, min(int(match.group(1)), int(self.config.max_rows)))

    def _aggregate_by_dimension(
        self,
        rows: list[dict[str, Any]],
        dimension: str,
        metric: str,
        *,
        aggregation: str = "sum",
    ) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for row in rows:
            dimension_value = str(row.get(dimension, "")).strip()
            metric_value = 1.0 if aggregation == "count" else self._parse_number(row.get(metric))
            if not dimension_value or metric_value is None:
                continue
            bucket = buckets.setdefault(
                dimension_value,
                {"dimension": dimension_value, "value": 0.0, "count": 0, "sum": 0.0},
            )
            bucket["sum"] = round(float(bucket["sum"]) + metric_value, 6)
            bucket["value"] = bucket["sum"]
            bucket["count"] = int(bucket["count"]) + 1
        if aggregation == "avg":
            for bucket in buckets.values():
                bucket["value"] = round(float(bucket["sum"]) / max(1, int(bucket["count"])), 6)
        return list(buckets.values())

    @staticmethod
    def _render_query_result(query_result: dict[str, Any]) -> str:
        metric = query_result.get("metric", "")
        dimension = query_result.get("dimension", "")
        rows = query_result.get("rows", [])
        aggregation = query_result.get("aggregation", "sum")
        filters = query_result.get("filters") or []
        title = f"Query result: {query_result.get('intent')} {query_result.get('limit')} by {metric}"
        lines = [title]
        if filters:
            filter_text = "; ".join(
                f"{item.get('column')} {item.get('operator')} {item.get('value')}" for item in filters
            )
            lines.append(f"Filters: {filter_text}")
        if query_result.get("operation") == "filtered_empty":
            lines.append("- No rows matched the requested filters.")
            return "\n".join(lines)
        for index, row in enumerate(rows[:10], start=1):
            if dimension:
                lines.append(
                    f"- {index}. {row.get('dimension')}: {row.get('value')} "
                    f"({aggregation}, {row.get('count')} rows)"
                )
            else:
                label = ", ".join(
                    f"{key}={value}" for key, value in row.items() if key != metric
                )
                lines.append(f"- {index}. {metric}={row.get(metric)}; {label}")
        return "\n".join(lines)

    @staticmethod
    def _infer_query_intent(request: str) -> str:
        text = str(request or "").strip().lower()
        if not text:
            return "none"
        if any(
            token in text
            for token in (
                "\u6700\u4f4e",
                "\u6700\u5c11",
                "bottom",
                "lowest",
                "least",
                "min",
            )
        ):
            return "bottom"
        if any(
            token in text
            for token in (
                "\u6700\u9ad8",
                "\u6700\u591a",
                "\u6700\u5927",
                "\u524d",
                "top",
                "highest",
                "most",
                "max",
            )
        ):
            return "top"
        if any(
            token in text
            for token in (
                "average",
                "avg",
                "mean",
                "sum",
                "total",
                "count",
                "group by",
                "by ",
                "\u5e73\u5747",
                "\u6c47\u603b",
                "\u5408\u8ba1",
                "\u8ba1\u6570",
                "\u6309",
            )
        ):
            return "aggregate"
        return "none"

    def _extract_query_limit(self, request: str) -> int:
        text = str(request or "")
        match = re.search(r"(?:top|\u524d|\u672b\u5c3e|bottom)\s*(\d{1,3})", text, flags=re.IGNORECASE)
        if not match:
            match = re.search(
                r"(\d{1,3})\s*(?:\u4e2a|\u6761|rows?|records?)",
                text,
                flags=re.IGNORECASE,
            )
        if not match:
            return max(1, int(self.config.default_query_limit))
        return max(1, min(int(match.group(1)), int(self.config.max_rows)))

    def _extract_filters(self, request: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
        return [item for group in self._extract_filter_groups(request, profile) for item in group]

    def _extract_filter_groups(self, request: str, profile: dict[str, Any]) -> list[list[dict[str, Any]]]:
        text = str(request or "")
        if not text.strip():
            return []

        groups: list[list[dict[str, Any]]] = []
        for chunk in self._split_or_filter_chunks(text, profile):
            filters = self._extract_filters_from_text(chunk, profile)
            if filters:
                groups.append(filters)
        return groups

    def _split_or_filter_chunks(self, text: str, profile: dict[str, Any]) -> list[str]:
        columns = [str(column) for column in profile.get("columns", [])]
        if not columns:
            return [text]
        chunks = re.split(r"\s+(?:or|\u6216\u8005)\s+", text, flags=re.IGNORECASE)
        if len(chunks) <= 1:
            return [text]

        expanded: list[str] = [chunks[0]]
        last_column = ""
        for chunk in chunks:
            for column in columns:
                if re.search(rf"\b{re.escape(column)}\b", chunk, flags=re.IGNORECASE):
                    last_column = column
                    break
        for chunk in chunks[1:]:
            if any(re.search(rf"\b{re.escape(column)}\b", chunk, flags=re.IGNORECASE) for column in columns):
                expanded.append(chunk)
            elif last_column:
                expanded.append(f"{last_column} = {chunk}")
        return expanded or [text]

    def _extract_filters_from_text(self, text: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
        columns = [str(column) for column in profile.get("columns", [])]
        filters: list[dict[str, Any]] = []
        for column in columns:
            escaped = re.escape(column)
            range_patterns = [
                rf"\b{escaped}\b\s+(?:between|from|\u4ecb\u4e8e|\u5728)\s*(-?\d+(?:\.\d+)?)\s*(?:and|to|-|\u548c|\u5230)\s*(-?\d+(?:\.\d+)?)",
                rf"\b{escaped}\b\s*(?:\u533a\u95f4|\u8303\u56f4)?\s*(-?\d+(?:\.\d+)?)\s*(?:-|~|\u5230)\s*(-?\d+(?:\.\d+)?)",
            ]
            for pattern in range_patterns:
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    low = self._parse_number(match.group(1))
                    high = self._parse_number(match.group(2))
                    if low is None or high is None:
                        continue
                    filters.append(
                        {
                            "column": column,
                            "operator": "between",
                            "value": [min(low, high), max(low, high)],
                        }
                    )

            patterns = [
                rf"\b{escaped}\b\s*(>=|<=|!=|=|>|<)\s*['\"]?([^,'\"\n;]+)",
                rf"\b{escaped}\b\s+(?:is|equals?|contains|like|\u4e3a|\u662f|\u7b49\u4e8e|\u5305\u542b)\s+['\"]?([^,'\"\n;]+)",
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    if len(match.groups()) == 2:
                        operator = match.group(1)
                        value = match.group(2)
                    else:
                        raw_operator = match.group(0).lower()
                        operator = (
                            "contains"
                            if "contains" in raw_operator or "like" in raw_operator or "\u5305\u542b" in raw_operator
                            else "="
                        )
                        value = match.group(1)
                    value = self._clean_filter_value(value)
                    if value:
                        filters.append({"column": column, "operator": operator, "value": value})

            numeric_patterns = [
                (rf"\b{escaped}\b\s+(?:greater than|above|over|\u5927\u4e8e|\u8d85\u8fc7)\s*(-?\d+(?:\.\d+)?)", ">"),
                (rf"\b{escaped}\b\s+(?:less than|below|under|\u5c0f\u4e8e|\u4f4e\u4e8e)\s*(-?\d+(?:\.\d+)?)", "<"),
                (rf"\b{escaped}\b\s+(?:at least|\u4e0d\u5c11\u4e8e|\u5927\u4e8e\u7b49\u4e8e)\s*(-?\d+(?:\.\d+)?)", ">="),
                (rf"\b{escaped}\b\s+(?:at most|\u4e0d\u8d85\u8fc7|\u5c0f\u4e8e\u7b49\u4e8e)\s*(-?\d+(?:\.\d+)?)", "<="),
            ]
            for pattern, operator in numeric_patterns:
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    value = self._clean_filter_value(match.group(1))
                    if value:
                        filters.append({"column": column, "operator": operator, "value": value})

        unique_filters: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in filters:
            value_key = json.dumps(item.get("value"), sort_keys=True, ensure_ascii=True)
            key = (str(item["column"]), str(item["operator"]), value_key.lower())
            if key in seen:
                continue
            seen.add(key)
            unique_filters.append(item)
        return unique_filters

    @staticmethod
    def _clean_filter_value(value: Any) -> str:
        text = str(value or "").strip().strip("'\"` ")
        return re.split(
            r"\s+(?:and|or|by|group\s+by|\u6309|\u5e76\u4e14|\u6216\u8005)\s+",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

    def _normalize_filter_tree(self, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        if value.get("column"):
            return self._normalize_filter_condition(value)

        logic = str(value.get("logic") or "and").strip().lower()
        if logic not in {"and", "or"}:
            logic = "and"
        raw_conditions = value.get("conditions")
        if not isinstance(raw_conditions, list):
            return None
        conditions = [
            normalized
            for item in raw_conditions
            if (normalized := self._normalize_filter_tree(item)) is not None
        ]
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"logic": logic, "conditions": conditions}

    @staticmethod
    def _normalize_filter_condition(value: dict[str, Any]) -> dict[str, Any] | None:
        column = str(value.get("column") or "").strip()
        if not column or "value" not in value:
            return None
        operator = str(value.get("operator") or "=").strip().lower()
        operator = {"==": "=", "<>": "!=", "not in": "not_in"}.get(operator, operator)
        if operator not in {"=", "!=", ">", ">=", "<", "<=", "in", "not_in", "between", "contains"}:
            operator = "="

        expected = value.get("value")
        if operator in {"in", "not_in"} and not isinstance(expected, list):
            expected = [expected]
        return {"column": column, "operator": operator, "value": expected}

    def _filters_to_tree(self, raw_filters: Any) -> dict[str, Any] | None:
        if not isinstance(raw_filters, list):
            return None
        filters = [
            normalized
            for item in raw_filters
            if isinstance(item, dict) and (normalized := self._normalize_filter_condition(item)) is not None
        ]
        if not filters:
            return None
        if len(filters) == 1:
            return filters[0]
        return {"logic": "and", "conditions": filters}

    def _filter_groups_to_tree(self, raw_filter_groups: Any) -> dict[str, Any] | None:
        if not isinstance(raw_filter_groups, list):
            return None
        groups = [
            group
            for item in raw_filter_groups
            if (group := self._filters_to_tree(item)) is not None
        ]
        if not groups:
            return None
        if len(groups) == 1:
            return groups[0]
        return {"logic": "or", "conditions": groups}

    def _filter_tree_to_filter_groups(self, filter_tree: dict[str, Any] | None) -> list[list[dict[str, Any]]]:
        if not filter_tree:
            return []
        if filter_tree.get("column"):
            return [[filter_tree]]

        logic = str(filter_tree.get("logic") or "and").lower()
        conditions = filter_tree.get("conditions")
        if not isinstance(conditions, list):
            return []
        child_groups = [self._filter_tree_to_filter_groups(item) for item in conditions]
        child_groups = [groups for groups in child_groups if groups]
        if not child_groups:
            return []
        if logic == "or":
            return [group for groups in child_groups for group in groups]

        merged_groups: list[list[dict[str, Any]]] = [[]]
        for groups in child_groups:
            merged_groups = [left + right for left in merged_groups for right in groups]
        return merged_groups

    def _apply_filters(
        self,
        rows: list[dict[str, Any]],
        filters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return self._apply_filter_groups(rows, [filters] if filters else [])

    def _apply_filter_groups(
        self,
        rows: list[dict[str, Any]],
        filter_groups: list[list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if not filter_groups:
            return rows
        return [
            row
            for row in rows
            if any(all(self._row_matches_filter(row, item) for item in group) for group in filter_groups)
        ]

    def _apply_filter_tree(
        self,
        rows: list[dict[str, Any]],
        filter_tree: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if not filter_tree:
            return rows
        return [row for row in rows if self._row_matches_filter_tree(row, filter_tree)]

    def _row_matches_filter_tree(self, row: dict[str, Any], filter_tree: dict[str, Any]) -> bool:
        if filter_tree.get("column"):
            return self._row_matches_filter(row, filter_tree)
        logic = str(filter_tree.get("logic") or "and").lower()
        conditions = filter_tree.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            return True
        if logic == "or":
            return any(self._row_matches_filter_tree(row, item) for item in conditions)
        return all(self._row_matches_filter_tree(row, item) for item in conditions)

    def _row_matches_filter(self, row: dict[str, Any], filter_item: dict[str, Any]) -> bool:
        column = str(filter_item.get("column") or "")
        operator = str(filter_item.get("operator") or "=").lower()
        actual = row.get(column)
        actual_number = self._parse_number(actual)

        if operator == "between":
            raw_bounds = filter_item.get("value")
            if actual_number is None or not isinstance(raw_bounds, list):
                return False
            bounds = [
                number
                for number in (self._parse_number(value) for value in raw_bounds)
                if number is not None
            ]
            if len(bounds) != 2:
                return False
            return min(bounds) <= actual_number <= max(bounds)

        if operator in {"in", "not_in"}:
            raw_values = filter_item.get("value")
            expected_values = raw_values if isinstance(raw_values, list) else [raw_values]
            matches = any(self._values_equal(actual, expected) for expected in expected_values)
            return not matches if operator == "not_in" else matches

        expected = str(filter_item.get("value") or "").strip()
        expected_number = self._parse_number(expected)
        if operator in {">", ">=", "<", "<="}:
            if actual_number is None or expected_number is None:
                return False
            if operator == ">":
                return actual_number > expected_number
            if operator == ">=":
                return actual_number >= expected_number
            if operator == "<":
                return actual_number < expected_number
            return actual_number <= expected_number

        actual_text = str(actual or "").strip().lower()
        expected_text = expected.lower()
        if operator in {"!=", "<>"}:
            return not self._values_equal(actual, expected)
        if operator == "contains":
            return expected_text in actual_text
        return self._values_equal(actual, expected)

    @classmethod
    def _values_equal(cls, actual: Any, expected: Any) -> bool:
        actual_number = cls._parse_number(actual)
        expected_number = cls._parse_number(expected)
        if actual_number is not None and expected_number is not None:
            return actual_number == expected_number
        return str(actual or "").strip().lower() == str(expected or "").strip().lower()

    def _build_dashboard_payload(
        self,
        profile: dict[str, Any],
        *,
        chart_spec: dict[str, Any] | None,
        query_result: dict[str, Any] | None,
        source_label: str,
    ) -> dict[str, Any] | None:
        evidence = [
            {
                "id": "d1",
                "title": source_label or "Data Agent dataset",
                "snippet": (
                    f"Rows: {profile.get('row_count', 0)}; "
                    f"columns: {', '.join(profile.get('columns', [])[:8])}"
                ),
                "source_type": "dataset",
            }
        ]
        sampling = profile.get("sampling")
        if isinstance(sampling, dict) and sampling.get("sampled"):
            evidence[0]["snippet"] = (
                f"Sampled rows: {sampling.get('sampled_row_count', profile.get('row_count', 0))} "
                f"of {sampling.get('row_count', profile.get('row_count', 0))}; "
                f"columns: {', '.join(profile.get('columns', [])[:8])}"
            )
        metrics = [
            {
                "label": "Rows",
                "value": profile.get("row_count", 0),
                "trend": "flat",
                "highlight": True,
                "evidence_ids": ["d1"],
            },
            {
                "label": "Columns",
                "value": profile.get("column_count", 0),
                "trend": "flat",
                "evidence_ids": ["d1"],
            },
        ]
        for column, stats in list((profile.get("numeric_columns") or {}).items())[:4]:
            metrics.append(
                {
                    "label": f"{column} sum",
                    "value": stats.get("sum", 0),
                    "trend": "flat",
                    "evidence_ids": ["d1"],
                }
            )

        charts = []
        if chart_spec:
            metric = str(chart_spec.get("metric") or "Metric")
            dimension = str(chart_spec.get("dimension") or "Dimension")
            charts.append(
                {
                    "title": f"{metric} by {dimension}",
                    "type": chart_spec.get("type", "bar"),
                    "description": "Generated by Data Agent from structured data.",
                    "evidence_ids": ["d1"],
                    "chart_data": {
                        "type": chart_spec.get("type", "bar"),
                        "labels": chart_spec.get("labels", []),
                        "datasets": chart_spec.get("datasets", []),
                    },
                }
            )

        preview_rows = profile.get("preview_rows", [])
        columns = [str(column) for column in profile.get("columns", [])[:8]]
        table = None
        if columns and preview_rows:
            table = {
                "title": "Preview rows",
                "columns": columns,
                "rows": [
                    {column: self._dashboard_cell(row.get(column)) for column in columns}
                    for row in preview_rows[:8]
                ],
                "evidence_ids": ["d1"],
            }

        summary_parts = [
            f"Profiled {profile.get('row_count', 0)} rows across {profile.get('column_count', 0)} columns."
        ]
        if query_result:
            summary_parts.append(
                f"Applied {query_result.get('intent')} query on {query_result.get('metric')}."
            )
        warnings = []
        missing_columns = [
            column
            for column, count in profile.get("missing_by_column", {}).items()
            if count
        ]
        if missing_columns:
            warnings.append(f"Missing values detected in: {', '.join(missing_columns[:5])}.")

        return {
            "title": "Data Agent Dashboard",
            "summary": " ".join(summary_parts),
            "metrics": metrics,
            "charts": charts,
            "table": table,
            "evidence": evidence,
            "warnings": warnings,
        }

    @staticmethod
    def _dashboard_cell(value: Any) -> str | int | float:
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, float, str)):
            return value
        return str(value)

    @staticmethod
    def _render_dashboard_block(payload: dict[str, Any]) -> str:
        return f":::dashboard-card\n{json.dumps(payload, ensure_ascii=False)}\n:::"

    def _fallback_output(self, request: str, context: dict[str, Any]) -> str:
        upstream = self._upstream_text(context)
        basis = upstream or request or "No structured rows provided."
        return (
            "Data Agent Analysis\n\n"
            "No tabular dataset was found in the current task context. "
            "Provide rows, records, JSON, or CSV content for statistical profiling.\n\n"
            f"Analysis basis:\n{basis}"
        )

    def _upstream_text(self, context: dict[str, Any]) -> str:
        results = context.get("_agent_results")
        if not isinstance(results, dict):
            return ""
        parts: list[str] = []
        for result in results.values():
            if not isinstance(result, dict):
                continue
            agent = str(result.get("agent") or "agent").strip()
            output = str(result.get("output") or "").strip()
            if output:
                parts.append(f"## {agent}\n{output}")
        text = "\n\n".join(parts).strip()
        limit = max(1000, int(self.config.max_context_chars))
        return text[:limit].strip()

    async def _summarize_with_llm(
        self,
        request: str,
        profile: dict[str, Any],
        fallback_output: str,
    ) -> str:
        prompt = (
            "You are a data analysis agent. Summarize this tabular profile in concise Markdown. "
            "Do not invent numbers beyond the profile.\n\n"
            f"User request:\n{request}\n\n"
            f"Profile JSON:\n{json.dumps(profile, ensure_ascii=False)}\n\n"
            f"Deterministic analysis:\n{fallback_output}"
        )
        response = await asyncio.wait_for(
            self.llm.ainvoke(prompt),
            timeout=max(1.0, float(self.config.timeout_seconds)),
        )
        return str(getattr(response, "content", response) or "").strip() or fallback_output

    @staticmethod
    def _sources(source_label: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not source_label or not rows:
            return []
        return [
            {
                "type": "dataset",
                "title": source_label,
                "row_count": len(rows),
            }
        ]


__all__ = ["DataAnalysisAgent", "DataAnalysisAgentConfig"]
