import asyncio
from types import SimpleNamespace

import pytest

import backend.deck_service as deck_service
from backend.helpers.deck_report_helpers import build_create_deck_kwargs
from backend.helpers.deck_route_helpers import create_deck_artifact_result


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
