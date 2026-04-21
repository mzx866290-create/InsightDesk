import asyncio
from types import SimpleNamespace

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

import backend.deck_service as deck_service


def _messages():
    return [
        HumanMessage(content="请把这次调研结果整理成汇报要点"),
        AIMessage(content="核心结论已经明确，可以直接按主题、问题、建议三部分生成演示稿。"),
    ]


def _panel_config():
    return SimpleNamespace(
        panel_id="panel-main",
        provider="local",
        model="test-model",
        base_url="http://localhost:11434",
        api_key="",
        temperature=0.3,
    )


def _install_fake_generation(monkeypatch):
    monkeypatch.setattr(deck_service, "get_llm", lambda **kwargs: object())

    async def fake_generate_outline(
        llm,
        pack,
        target_slide_count,
        content_slide_count,
        system_prompt,
    ):
        assert pack.source_mode == "chat_only"
        assert content_slide_count == 2
        return deck_service.OutlinePlan(
            title="调研结论汇报",
            subtitle="基于回答内容自动整理",
            core_message="可以在证据不足时先基于回答生成草稿。",
            sections=["结论概览", "问题拆解", "行动建议"],
            content_slides=[
                deck_service.OutlineSlidePlan(
                    title="结论概览",
                    objective="概括本次回答里的核心判断",
                    section="结论概览",
                    evidence_source_ids=[],
                ),
                deck_service.OutlineSlidePlan(
                    title="行动建议",
                    objective="整理可执行建议",
                    section="行动建议",
                    evidence_source_ids=[],
                ),
            ],
        )

    async def fake_generate_content_slides(llm, pack, outline, system_prompt):
        assert pack.source_mode == "chat_only"
        return deck_service.DraftedSlideBundle(
            content_slides=[
                deck_service.DraftedContentSlide(
                    title="结论概览",
                    subtitle="先把关键判断讲清楚",
                    key_points=[
                        "回答内容已经覆盖主题、问题和建议三层结构。",
                        "即使知识库证据不足，也可以先产出可编辑草稿。",
                    ],
                    speaker_notes="这一页强调先形成结构化表达，再补充证据。",
                    quality_state="manual",
                ),
                deck_service.DraftedContentSlide(
                    title="行动建议",
                    subtitle="人工复核后再导出正式版本",
                    key_points=[
                        "保留人工复核提示，避免把弱证据内容直接当成定稿。",
                        "支持后续再补知识库来源和引用页。",
                    ],
                    speaker_notes="这一页提醒用户当前版本更适合继续编辑。",
                    quality_state="manual",
                ),
            ]
        )

    monkeypatch.setattr(deck_service, "_generate_outline", fake_generate_outline)
    monkeypatch.setattr(deck_service, "_generate_content_slides", fake_generate_content_slides)


def test_build_deck_falls_back_to_chat_only_when_kb_has_single_source(monkeypatch):
    class SingleSourcePipeline:
        def __init__(self, vector_store_path):
            self.vector_store_path = vector_store_path
            self.call_count = 0

        def load_store(self):
            return True

        def search_with_rerank(self, query, k, fetch_k):
            self.call_count += 1
            return [
                Document(
                    page_content=f"第{self.call_count}段来自同一来源的支撑信息",
                    metadata={"source": "single-source.md", "doc_id": "doc-1"},
                )
            ]

    _install_fake_generation(monkeypatch)
    monkeypatch.setattr(deck_service, "DocPipeline", SingleSourcePipeline)

    deck = asyncio.run(
        deck_service.build_deck(
            session_id="session-single-source",
            messages=_messages(),
            panel_config=_panel_config(),
            knowledge_base_enabled=True,
            target_slide_count=6,
            vector_store_path="vector_store/test-kb",
            system_prompt="你是专业汇报助手",
        )
    )

    warning_codes = {warning.code for warning in deck.generation.warnings}

    assert deck.meta.source_mode == "chat_only"
    assert deck.generation.source == "chat_only"
    assert deck.generation.actual_slide_count == 4
    assert "kb_insufficient_source_coverage" in warning_codes
    assert "chat_only_mode" in warning_codes
    assert "manual_review_required" in warning_codes
    assert deck.source_registry == []
    assert all(slide.quality_state == "manual" for slide in deck.slides)
    assert all(not slide.evidence_refs for slide in deck.slides)
    assert all(slide.type != "appendix_sources" for slide in deck.slides)


def test_build_deck_falls_back_to_chat_only_when_kb_unavailable(monkeypatch):
    class UnavailablePipeline:
        def __init__(self, vector_store_path):
            self.vector_store_path = vector_store_path

        def load_store(self):
            return False

    _install_fake_generation(monkeypatch)
    monkeypatch.setattr(deck_service, "DocPipeline", UnavailablePipeline)

    deck = asyncio.run(
        deck_service.build_deck(
            session_id="session-kb-unavailable",
            messages=_messages(),
            panel_config=_panel_config(),
            knowledge_base_enabled=True,
            target_slide_count=6,
            vector_store_path="vector_store/test-kb",
            system_prompt="你是专业汇报助手",
        )
    )

    warning_codes = {warning.code for warning in deck.generation.warnings}

    assert deck.meta.source_mode == "chat_only"
    assert "kb_unavailable_fallback" in warning_codes
    assert "chat_only_mode" in warning_codes
    assert "manual_review_required" in warning_codes


def test_chat_only_serialization_keeps_full_recent_answer_content():
    tail_marker = "TAIL_MARKER_CHAT_ONLY_FULL_ANSWER"
    answer = "\n".join(
        [
            "一、列表页优化",
            "头像建议",
            "建议使用白底或浅蓝底正装职业照。",
            "二、简历重写版",
            "个人优势",
            "电子信息工程专业背景，熟悉 Python、RPA 与办公自动化工具。",
            tail_marker,
        ]
    )
    messages = [
        HumanMessage(content="帮我把这段回答整理成 PPT"),
        AIMessage(content=answer),
    ]

    pack = deck_service._build_source_pack(
        session_id="session-chat-only-serialize",
        messages=messages,
        knowledge_base_enabled=False,
        vector_store_path=None,
        target_slide_count=8,
    )
    serialized = deck_service._serialize_source_pack(pack)

    assert pack.source_mode == "chat_only"
    assert "最近成功问答原文" in serialized
    assert "回答原文" in serialized
    assert tail_marker in serialized
