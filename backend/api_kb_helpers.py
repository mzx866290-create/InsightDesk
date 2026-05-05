"""Compatibility re-export for ``backend.helpers.kb_helpers``."""

from backend.helpers.kb_helpers import (
    filter_kb_chunks,
    kb_collect_chunks,
    kb_docstore_dict,
    kb_rebuild_from_documents,
    kb_safe_metadata,
)

__all__ = [
    "filter_kb_chunks",
    "kb_collect_chunks",
    "kb_docstore_dict",
    "kb_rebuild_from_documents",
    "kb_safe_metadata",
]
