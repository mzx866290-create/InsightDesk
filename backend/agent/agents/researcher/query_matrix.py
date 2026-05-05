"""Stage 4: query matrix generation."""

from __future__ import annotations

from collections import defaultdict

from search_runtime.types import ResearchPlan, ResearchQuery


BUCKET_ORDER = ("official", "policy", "reports", "news", "data")


def build_query_matrix(plan: ResearchPlan) -> dict[str, list[ResearchQuery]]:
    """Group planned queries by source intent bucket in a stable execution order."""
    grouped: dict[str, list[ResearchQuery]] = defaultdict(list)
    for query in plan.queries:
        bucket = str(query.bucket or "news").strip() or "news"
        grouped[bucket].append(query)

    ordered: dict[str, list[ResearchQuery]] = {}
    for bucket in BUCKET_ORDER:
        if grouped.get(bucket):
            ordered[bucket] = grouped[bucket]
    for bucket in sorted(set(grouped) - set(BUCKET_ORDER)):
        ordered[bucket] = grouped[bucket]
    return ordered


def flatten_query_matrix(matrix: dict[str, list[ResearchQuery]]) -> list[ResearchQuery]:
    """Flatten a query matrix while preserving bucket priority."""
    flattened: list[ResearchQuery] = []
    for bucket in [*BUCKET_ORDER, *sorted(set(matrix) - set(BUCKET_ORDER))]:
        flattened.extend(matrix.get(bucket, []))
    return flattened


__all__ = ["BUCKET_ORDER", "build_query_matrix", "flatten_query_matrix"]
