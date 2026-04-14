import asyncio
import io
from types import SimpleNamespace

from pptx import Presentation
from langchain_core.messages import AIMessage, HumanMessage

import deck_service


def _panel_config():
    return SimpleNamespace(
        panel_id="panel-main",
        provider="local",
        model="test-model",
        base_url="http://localhost:11434",
        api_key="",
        temperature=0.3,
    )


def _messages():
    return [
        HumanMessage(content="请把这次复盘整理成演示稿"),
        AIMessage(content="先讲结论，再展开风险与行动建议。"),
    ]


def _deck(slide_title: str, *, theme: str = "default"):
    return deck_service.DeckSpec(
        deck_id="deck-test",
        meta=deck_service.DeckMeta(
            title="季度经营复盘",
            subtitle="聚焦风险与行动",
            theme=theme,
            created_at="2026-04-04T10:00:00+0800",
            session_id="session-1",
            source_mode="chat_only",
            generator_panel_id="panel-main",
            author="tester",
            audience="leadership",
            purpose="review",
        ),
        generation=deck_service.DeckGeneration(
            source="chat_only",
            target_slide_count=4,
            actual_slide_count=4,
        ),
        slides=[
            deck_service.DeckSlide(
                id="slide_cover",
                type="cover",
                title="季度经营复盘",
                subtitle="聚焦风险与行动",
                layout="hero-title",
                blocks=[
                    deck_service.DeckBlock(
                        id="cover-block",
                        kind="paragraph",
                        role="core_message",
                        content={"text": "先讲总览。"},
                    )
                ],
            ),
            deck_service.DeckSlide(
                id="slide_outline",
                type="outline",
                title="汇报结构",
                subtitle="先总览，再拆解",
                layout="title-bullets",
                blocks=[
                    deck_service.DeckBlock(
                        id="outline-block",
                        kind="bullet_list",
                        role="outline",
                        content={"items": ["整体表现", "核心风险", "行动建议"]},
                    )
                ],
            ),
            deck_service.DeckSlide(
                id="slide_content_1",
                type="content",
                title=slide_title,
                subtitle="旧副标题",
                layout="title-bullets",
                intent="risk-review",
                speaker_notes="旧讲稿",
                blocks=[
                    deck_service.DeckBlock(
                        id="content-block",
                        kind="bullet_list",
                        role="main_points",
                        content={"items": ["旧要点 1", "旧要点 2"]},
                    )
                ],
                quality_state="manual",
                status=deck_service.DeckSlideStatus(review_state="draft"),
            ),
            deck_service.DeckSlide(
                id="slide_content_2",
                type="content",
                title="第二页",
                subtitle="第二页副标题",
                layout="title-bullets",
                intent="actions",
                speaker_notes="第二页讲稿",
                blocks=[
                    deck_service.DeckBlock(
                        id="content-block-2",
                        kind="bullet_list",
                        role="main_points",
                        content={"items": ["行动 1", "行动 2"]},
                    )
                ],
                quality_state="manual",
                status=deck_service.DeckSlideStatus(review_state="draft"),
            ),
        ],
        source_registry=[],
    )


def test_export_deck_to_pptx_uses_selected_theme_palette():
    deck = _deck("第一页", theme="midnight")

    pptx_bytes = deck_service.export_deck_to_pptx(deck)
    presentation = Presentation(io.BytesIO(pptx_bytes))

    assert str(presentation.slides[0].background.fill.fore_color.rgb) == "111827"


def test_regenerate_deck_slide_keeps_slot_and_updates_review_state(monkeypatch):
    current_deck = _deck("旧第一页", theme="sunrise")
    regenerated_deck = _deck("新第一页", theme="sunrise")
    regenerated_deck.slides[2].subtitle = "新的副标题"
    regenerated_deck.slides[2].speaker_notes = "新的讲稿"
    regenerated_deck.slides[2].blocks = [
        deck_service.DeckBlock(
            id="new-block",
            kind="bullet_list",
            role="main_points",
            content={"items": ["新要点 1", "新要点 2", "新要点 3"]},
        )
    ]
    regenerated_deck.slides[2].quality_state = "supported"

    async def fake_build_deck(**kwargs):
        assert kwargs["theme"] == "sunrise"
        return regenerated_deck

    monkeypatch.setattr(deck_service, "build_deck", fake_build_deck)

    slide = asyncio.run(
        deck_service.regenerate_deck_slide(
            deck=current_deck,
            slide_id="slide_content_1",
            messages=_messages(),
            panel_config=_panel_config(),
            knowledge_base_enabled=False,
        )
    )

    assert slide.id == "slide_content_1"
    assert slide.title == "新第一页"
    assert slide.subtitle == "新的副标题"
    assert slide.quality_state == "supported"
    assert slide.status.review_state == "regenerated"
    assert slide.status.dirty is False
