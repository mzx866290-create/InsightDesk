from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.helpers.artifact_export_route_helpers import (
    export_artifact_response,
    report_artifact_qa_pairs,
)
from backend.helpers.deck_report_helpers import DeckExportGateError


def _disposition(filename: str) -> str:
    return f'attachment; filename="{filename}"'


def _report_artifact(**overrides):
    values = {
        "artifact_type": "report",
        "title": "Board Update",
        "content": {
            "markdown": "# Board Update",
            "qa_pairs": [{"question": "Q", "answer": "A"}],
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _deck_artifact(**overrides):
    values = {
        "artifact_type": "deck",
        "title": "Deck",
        "linked_resource_id": "deck-1",
        "content": {"deck_id": "deck-from-content"},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _export_response(artifact, **overrides):
    options = {
        "artifact": artifact,
        "export_format": "",
        "get_deck": lambda deck_id: SimpleNamespace(deck_id=deck_id),
        "export_deck_payload": lambda deck, **kwargs: {
            "content": b"pptx",
            "filename": f"{deck.deck_id}.pptx",
        },
        "export_deck_to_pptx": lambda deck: b"pptx",
        "build_export_filename": lambda deck, extension: f"{deck.deck_id}.{extension}",
        "build_download_content_disposition": _disposition,
        "safe_report_filename": lambda title: title.replace(" ", "_"),
        "populate_chat_report_presentation": lambda *args, **kwargs: None,
    }
    options.update(overrides)
    return export_artifact_response(**options)


def test_export_artifact_response_returns_report_markdown_response():
    response = _export_response(_report_artifact(), export_format="md")

    assert response.status_code == 200
    assert response.body == b"# Board Update"
    assert response.media_type == "text/markdown; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="Board_Update.md"'
    )


def test_report_artifact_qa_pairs_filters_blank_and_non_dict_entries():
    artifact = _report_artifact(
        content={
            "qa_pairs": [
                {"question": " Q ", "answer": " A "},
                {"question": " ", "answer": ""},
                "invalid",
            ]
        }
    )

    assert report_artifact_qa_pairs(artifact) == [("Q", "A")]


def test_export_artifact_response_rejects_report_pptx_without_pairs():
    with pytest.raises(HTTPException) as exc_info:
        _export_response(_report_artifact(content={"qa_pairs": []}), export_format="pptx")

    assert exc_info.value.status_code == 400
    assert "no exportable content" in str(exc_info.value.detail)


def test_export_artifact_response_exports_deck_pptx_by_linked_resource_id():
    captured = {}

    response = _export_response(
        _deck_artifact(),
        export_format="pptx",
        get_deck=lambda deck_id: SimpleNamespace(deck_id=deck_id),
        export_deck_payload=lambda deck, **kwargs: captured.setdefault(
            "payload",
            {
                "content": f"deck:{deck.deck_id}".encode("utf-8"),
                "filename": f"{deck.deck_id}.pptx",
            },
        ),
    )

    assert response.body == b"deck:deck-1"
    assert response.headers["content-disposition"] == 'attachment; filename="deck-1.pptx"'


def test_export_artifact_response_maps_deck_export_gate_to_conflict():
    def blocked_export(*args, **kwargs):
        raise DeckExportGateError({"blocked": True})

    with pytest.raises(HTTPException) as exc_info:
        _export_response(_deck_artifact(), export_deck_payload=blocked_export)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {"blocked": True}
