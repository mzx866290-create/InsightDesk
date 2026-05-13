"""Compatibility helpers for deck/report API payloads."""

from backend.helpers.deck_report_helpers import (
    DeckExportGateError,
    apply_deck_template_metadata,
    attach_deck_delivery_audit,
    apply_deck_update,
    build_deck_delivery_response,
    build_deck_evidence_review_payload,
    build_create_deck_kwargs,
    build_regenerate_deck_kwargs,
    build_scoped_report_messages,
    create_share_link_payload,
    export_deck_payload,
    replace_deck_slide,
    report_download_payload,
    report_markdown_payload,
    resolve_report_messages,
    update_deck_block_refs,
)


__all__ = [
    "DeckExportGateError",
    "apply_deck_template_metadata",
    "attach_deck_delivery_audit",
    "apply_deck_update",
    "build_deck_delivery_response",
    "build_deck_evidence_review_payload",
    "build_create_deck_kwargs",
    "build_regenerate_deck_kwargs",
    "build_scoped_report_messages",
    "create_share_link_payload",
    "export_deck_payload",
    "replace_deck_slide",
    "report_download_payload",
    "report_markdown_payload",
    "resolve_report_messages",
    "update_deck_block_refs",
]
