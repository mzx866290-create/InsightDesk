import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import backend.deck_service as deck_service
from backend.helpers.deck_report_helpers import DeckExportGateError
from backend.helpers.deck_report_helpers import build_create_deck_kwargs
from backend.helpers.deck_route_helpers import DECK_EXPORT_UNSUPPORTED_DETAIL
from backend.helpers.deck_route_helpers import DECK_SLIDE_NOT_FOUND_DETAIL
from backend.helpers.deck_route_helpers import DECK_SOURCE_MESSAGES_NOT_FOUND_DETAIL
from backend.helpers.deck_route_helpers import DECK_SOURCE_SCOPE_NOT_FOUND_DETAIL
from backend.helpers.deck_route_helpers import DECK_MUST_KEEP_SLIDE_DETAIL
from backend.helpers.deck_route_helpers import create_deck_artifact_result
from backend.helpers.deck_route_helpers import export_deck_response
from backend.helpers.deck_route_helpers import grant_created_deck_artifact_access
from backend.helpers.deck_route_helpers import regenerate_deck_slide_result
from backend.helpers.deck_route_helpers import update_deck_block_refs_result
from backend.helpers.deck_route_helpers import update_deck_result


class _Dumpable(SimpleNamespace):
    def model_dump(self, *, mode):
        assert mode == "json"
        return dict(self.payload)


def _deck(deck_id: str = "deck-helper") -> deck_service.DeckSpec:
    return deck_service.DeckSpec(
        deck_id=deck_id,
        meta=deck_service.DeckMeta(
            title="Board Update",
            subtitle="Q2 snapshot",
            theme="default",
            created_at="2026-04-16T10:00:00+0800",
            session_id="session-1",
            source_mode="chat_only",
            generator_panel_id="panel-main",
            author="tester",
            audience="leaders",
            purpose="briefing",
        ),
        generation=deck_service.DeckGeneration(
            source="chat_only",
            target_slide_count=2,
            actual_slide_count=2,
        ),
        slides=[
            deck_service.DeckSlide(
                id="cover",
                type="cover",
                title="Board Update",
                subtitle="Q2 snapshot",
                layout="hero-title",
                blocks=[],
            )
        ],
        source_registry=[],
    )


def _request(**overrides):
    values = {
        "session_id": "session-1",
        "panel_config": {"panel_id": "panel-main"},
        "knowledge_base_enabled": False,
        "target_slide_count": 2,
        "theme": "default",
        "answer_group_id": " answer-1 ",
        "panel_id": " panel-main ",
        "template_id": "board_deck",
        "template_options": {"theme": "midnight", "nested": {"ignored": True}},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_create_deck_artifact_result_builds_deck_and_payload():
    saved_decks = []
    captured = {}

    async def fake_build_deck(**kwargs):
        captured.update(kwargs)
        deck = _deck("deck-created")
        deck.meta.session_id = kwargs["session_id"]
        deck.meta.source_answer_group_id = kwargs["source_answer_group_id"]
        deck.meta.source_panel_id = kwargs["source_panel_id"]
        return deck

    result = asyncio.run(
        create_deck_artifact_result(
            request=_request(),
            messages=["message"],
            build_deck=fake_build_deck,
            build_create_deck_kwargs=build_create_deck_kwargs,
            resolve_active_prompt_runtime=lambda enabled: ("system", "vector-store", None),
            normalize_deck_theme=lambda value: f"theme:{value}",
            save_deck=saved_decks.append,
            create_deck_artifact=lambda deck: SimpleNamespace(
                artifact_id=f"artifact-{deck.deck_id}"
            ),
        ),
    )

    assert captured["messages"] == ["message"]
    assert captured["theme"] == "theme:default"
    assert captured["source_answer_group_id"] == "answer-1"
    assert captured["source_panel_id"] == "panel-main"
    assert saved_decks == [result.deck]
    assert result.deck_id == "deck-created"
    assert result.artifact_id == "artifact-deck-created"
    assert result.deck_payload["artifact_id"] == "artifact-deck-created"
    assert result.deck_payload["meta"]["template_id"] == "board_deck"
    assert result.deck_payload["meta"]["template_options"] == {"theme": "midnight"}


def test_create_deck_artifact_result_validates_template_before_building():
    build_called = False

    async def fake_build_deck(**kwargs):
        nonlocal build_called
        build_called = True
        return _deck()

    with pytest.raises(ValueError, match="not deck"):
        asyncio.run(
            create_deck_artifact_result(
                request=_request(template_id="executive_report"),
                messages=["message"],
                build_deck=fake_build_deck,
                build_create_deck_kwargs=build_create_deck_kwargs,
                resolve_active_prompt_runtime=lambda enabled: (
                    "system",
                    "vector-store",
                    None,
                ),
                normalize_deck_theme=lambda value: value,
                save_deck=lambda deck: None,
                create_deck_artifact=lambda deck: SimpleNamespace(artifact_id="artifact-1"),
            )
        )

    assert build_called is False


def test_grant_created_deck_artifact_access_inherits_and_grants_owner():
    inherited = []
    owners = []

    def inherit_resource_grants(**kwargs):
        inherited.append(kwargs)

    def grant_resource_owner(request, **kwargs):
        owners.append({"request": request, **kwargs})

    request = SimpleNamespace(user="editor")
    access_store = object()

    grant_created_deck_artifact_access(
        request=request,
        session_id="session-1",
        deck_id="deck-1",
        artifact_id="artifact-1",
        access_store=access_store,
        require_remote_editor=lambda req: {"role": "editor"},
        audit_security_event=lambda *args, **kwargs: None,
        inherit_resource_grants=inherit_resource_grants,
        grant_resource_owner=grant_resource_owner,
        now=lambda: 123.0,
    )

    assert [
        (item["target_resource_type"], item["target_resource_id"])
        for item in inherited
    ] == [("deck", "deck-1"), ("artifact", "artifact-1")]
    assert all(item["source_resource_type"] == "session" for item in inherited)
    assert all(item["source_resource_id"] == "session-1" for item in inherited)
    assert [item["resource_type"] for item in owners] == ["deck", "artifact"]
    assert [item["resource_id"] for item in owners] == ["deck-1", "artifact-1"]
    assert all(item["request"] is request for item in owners)


def test_update_deck_result_applies_update_saves_and_syncs():
    deck = _Dumpable(payload={"deck_id": "deck-1", "title": "Before"})
    request = SimpleNamespace(slides=None)
    calls = []

    def apply_deck_update(deck_arg, request_arg, *, normalize_deck_theme):
        assert deck_arg is deck
        assert request_arg is request
        assert normalize_deck_theme("default") == "theme:default"
        deck_arg.payload["title"] = "After"
        calls.append("apply")

    payload = update_deck_result(
        deck=deck,
        request=request,
        apply_deck_update=apply_deck_update,
        normalize_deck_theme=lambda value: f"theme:{value}",
        save_deck=lambda deck_arg: calls.append(("save", deck_arg)),
        sync_deck_artifacts=lambda deck_arg: calls.append(("sync", deck_arg)),
    )

    assert payload == {"deck_id": "deck-1", "title": "After"}
    assert calls == ["apply", ("save", deck), ("sync", deck)]


def test_update_deck_result_rejects_empty_slide_updates():
    with pytest.raises(HTTPException) as exc_info:
        update_deck_result(
            deck=_Dumpable(payload={"deck_id": "deck-1"}),
            request=SimpleNamespace(slides=[]),
            apply_deck_update=lambda *args, **kwargs: None,
            normalize_deck_theme=lambda value: value,
            save_deck=lambda deck: None,
            sync_deck_artifacts=lambda deck: None,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == DECK_MUST_KEEP_SLIDE_DETAIL


def test_update_deck_block_refs_result_updates_saves_syncs_and_serializes():
    deck = _Dumpable(payload={"deck_id": "deck-1"})
    block = _Dumpable(payload={"id": "block-1", "content": {"evidence_ref_ids": ["ref-1"]}})
    calls = []

    def update_deck_block_refs(deck_arg, slide_id, block_id, payload):
        assert deck_arg is deck
        assert slide_id == "slide-1"
        assert block_id == "block-1"
        assert payload == {"evidence_ref_ids": ["ref-1"]}
        calls.append("update")
        return {
            "deck": deck,
            "slide_id": slide_id,
            "block_id": block_id,
            "block": block,
            "citation_validation": {"status": "ok"},
            "evidence_review": {"status": "supported"},
            "export_gate": {"blocked": False},
            "slide_delivery": {"slide_id": slide_id},
        }

    result = update_deck_block_refs_result(
        deck=deck,
        slide_id="slide-1",
        block_id="block-1",
        payload={"evidence_ref_ids": ["ref-1"]},
        update_deck_block_refs=update_deck_block_refs,
        save_deck=lambda deck_arg: calls.append(("save", deck_arg)),
        sync_deck_artifacts=lambda deck_arg: calls.append(("sync", deck_arg)),
    )

    assert result == {
        "deck": {"deck_id": "deck-1"},
        "slide_id": "slide-1",
        "block_id": "block-1",
        "block": {"id": "block-1", "content": {"evidence_ref_ids": ["ref-1"]}},
        "citation_validation": {"status": "ok"},
        "evidence_review": {"status": "supported"},
        "export_gate": {"blocked": False},
        "slide_delivery": {"slide_id": "slide-1"},
    }
    assert calls == ["update", ("save", deck), ("sync", deck)]


def test_regenerate_deck_slide_result_resolves_saved_scope_saves_and_syncs():
    deck = _deck("deck-regenerate")
    deck.meta.source_answer_group_id = "answer-1"
    deck.meta.source_panel_id = "panel-main"
    request = SimpleNamespace(panel_config="panel-config", knowledge_base_enabled=None)
    regenerated_slide = deck_service.DeckSlide(
        id="content-1",
        type="content",
        title="Regenerated",
        layout="title-bullets",
        blocks=[],
    )
    calls = []

    def create_chat_message_history(*, session_id):
        assert session_id == "session-1"
        return "history"

    def resolve_report_messages(history, *, answer_group_id, panel_id):
        assert history == "history"
        assert answer_group_id == "answer-1"
        assert panel_id == "panel-main"
        return ["message"]

    def build_regenerate_deck_kwargs(deck_arg, request_arg, **kwargs):
        assert deck_arg is deck
        assert request_arg is request
        assert kwargs["normalize_model_config"]("raw") == {"normalized": "raw"}
        assert kwargs["resolve_active_prompt_runtime"](False) == ("prompt", None, None)
        return {"panel_config": {"panel": "main"}, "knowledge_base_enabled": False}

    async def regenerate_deck_slide(**kwargs):
        assert kwargs["deck"] is deck
        assert kwargs["slide_id"] == "content-1"
        assert kwargs["messages"] == ["message"]
        assert kwargs["panel_config"] == {"panel": "main"}
        calls.append("regenerate")
        return regenerated_slide

    result = asyncio.run(
        regenerate_deck_slide_result(
            deck=deck,
            slide_id="content-1",
            request=request,
            create_chat_message_history=create_chat_message_history,
            resolve_report_messages=resolve_report_messages,
            build_regenerate_deck_kwargs=build_regenerate_deck_kwargs,
            normalize_model_config=lambda value: {"normalized": value},
            resolve_active_prompt_runtime=lambda enabled: ("prompt", None, None),
            regenerate_deck_slide=regenerate_deck_slide,
            replace_deck_slide=lambda deck_arg, slide: calls.append(("replace", deck_arg, slide)),
            save_deck=lambda deck_arg: calls.append(("save", deck_arg)),
            sync_deck_artifacts=lambda deck_arg: calls.append(("sync", deck_arg)),
            build_deck_delivery_response=lambda deck_arg, **kwargs: {
                "deck_id": deck_arg.deck_id,
                "focus_slide_id": kwargs["focus_slide_id"],
            },
        )
    )

    assert result == {"deck_id": "deck-regenerate", "focus_slide_id": "content-1"}
    assert calls == [
        "regenerate",
        ("replace", deck, regenerated_slide),
        ("save", deck),
        ("sync", deck),
    ]


def test_regenerate_deck_slide_result_maps_scope_and_slide_errors():
    deck = _deck("deck-regenerate-errors")
    request = SimpleNamespace(panel_config="panel-config", knowledge_base_enabled=None)

    with pytest.raises(HTTPException) as scope_exc:
        asyncio.run(
            regenerate_deck_slide_result(
                deck=deck,
                slide_id="content-1",
                request=request,
                create_chat_message_history=lambda **kwargs: "history",
                resolve_report_messages=lambda *args, **kwargs: (_ for _ in ()).throw(
                    KeyError("missing-scope")
                ),
                build_regenerate_deck_kwargs=lambda *args, **kwargs: {},
                normalize_model_config=lambda value: value,
                resolve_active_prompt_runtime=lambda enabled: (None, None, None),
                regenerate_deck_slide=lambda **kwargs: None,
                replace_deck_slide=lambda deck_arg, slide: None,
                save_deck=lambda deck_arg: None,
                sync_deck_artifacts=lambda deck_arg: None,
                build_deck_delivery_response=lambda *args, **kwargs: {},
            )
        )
    assert scope_exc.value.status_code == 404
    assert scope_exc.value.detail == DECK_SOURCE_SCOPE_NOT_FOUND_DETAIL

    with pytest.raises(HTTPException) as empty_exc:
        asyncio.run(
            regenerate_deck_slide_result(
                deck=deck,
                slide_id="content-1",
                request=request,
                create_chat_message_history=lambda **kwargs: "history",
                resolve_report_messages=lambda *args, **kwargs: [],
                build_regenerate_deck_kwargs=lambda *args, **kwargs: {},
                normalize_model_config=lambda value: value,
                resolve_active_prompt_runtime=lambda enabled: (None, None, None),
                regenerate_deck_slide=lambda **kwargs: None,
                replace_deck_slide=lambda deck_arg, slide: None,
                save_deck=lambda deck_arg: None,
                sync_deck_artifacts=lambda deck_arg: None,
                build_deck_delivery_response=lambda *args, **kwargs: {},
            )
        )
    assert empty_exc.value.status_code == 400
    assert empty_exc.value.detail == DECK_SOURCE_MESSAGES_NOT_FOUND_DETAIL

    async def missing_slide(**kwargs):
        raise KeyError("content-1")

    with pytest.raises(HTTPException) as slide_exc:
        asyncio.run(
            regenerate_deck_slide_result(
                deck=deck,
                slide_id="content-1",
                request=request,
                create_chat_message_history=lambda **kwargs: "history",
                resolve_report_messages=lambda *args, **kwargs: ["message"],
                build_regenerate_deck_kwargs=lambda *args, **kwargs: {},
                normalize_model_config=lambda value: value,
                resolve_active_prompt_runtime=lambda enabled: (None, None, None),
                regenerate_deck_slide=missing_slide,
                replace_deck_slide=lambda deck_arg, slide: None,
                save_deck=lambda deck_arg: None,
                sync_deck_artifacts=lambda deck_arg: None,
                build_deck_delivery_response=lambda *args, **kwargs: {},
            )
        )
    assert slide_exc.value.status_code == 404
    assert slide_exc.value.detail == DECK_SLIDE_NOT_FOUND_DETAIL


def test_export_deck_response_returns_pptx_download_response():
    deck = _deck("deck-export")
    captured = {}

    def export_deck_payload(deck_arg, **kwargs):
        captured["deck"] = deck_arg
        captured["kwargs"] = kwargs
        return {"content": b"pptx-bytes", "filename": "deck-export.pptx"}

    response = export_deck_response(
        deck=deck,
        export_format="pptx",
        export_deck_payload=export_deck_payload,
        export_deck_to_pptx=lambda deck_arg: b"pptx",
        build_export_filename=lambda deck_arg, extension: f"{deck_arg.deck_id}.{extension}",
        build_download_content_disposition=lambda filename: f'attachment; filename="{filename}"',
        allow_unsafe_export=True,
        override_reason="manual review",
    )

    assert response.body == b"pptx-bytes"
    assert response.media_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert response.headers["content-disposition"] == 'attachment; filename="deck-export.pptx"'
    assert captured["deck"] is deck
    assert captured["kwargs"]["allow_unsafe_export"] is True
    assert captured["kwargs"]["override_reason"] == "manual review"


def test_export_deck_response_maps_export_errors():
    deck = _deck("deck-export-errors")

    with pytest.raises(HTTPException) as format_exc:
        export_deck_response(
            deck=deck,
            export_format="pdf",
            export_deck_payload=lambda *args, **kwargs: {},
            export_deck_to_pptx=lambda deck_arg: b"",
            build_export_filename=lambda *args, **kwargs: "deck.pptx",
            build_download_content_disposition=lambda filename: filename,
        )
    assert format_exc.value.status_code == 400
    assert format_exc.value.detail == DECK_EXPORT_UNSUPPORTED_DETAIL

    def blocked_export(*args, **kwargs):
        raise DeckExportGateError({"blocked": True})

    with pytest.raises(HTTPException) as gate_exc:
        export_deck_response(
            deck=deck,
            export_format="pptx",
            export_deck_payload=blocked_export,
            export_deck_to_pptx=lambda deck_arg: b"",
            build_export_filename=lambda *args, **kwargs: "deck.pptx",
            build_download_content_disposition=lambda filename: filename,
        )
    assert gate_exc.value.status_code == 409
    assert gate_exc.value.detail == {"blocked": True}
