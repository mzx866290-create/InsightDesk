from backend.api_session_helpers import (
    build_answer_group_review_payload,
    collect_session_attachments,
    message_payload,
    render_shared_deck_html,
    render_shared_session_html,
)
from backend.deck_service import DeckBlock, DeckGeneration, DeckMeta, DeckSlide, DeckSpec


def test_message_payload_restores_role_and_metadata():
    payload = message_payload(
        {
            "id": 7,
            "type": "human",
            "content": "hello",
            "images": [{"name": "chart.png"}],
            "files": [{"name": "brief.txt"}],
            "sources": [{"title": "Source A"}],
            "model_id": "qwen-main",
            "panel_id": "panel-main",
            "answer_group_id": "grp-1",
            "workflow_nodes": [{"id": "node-1"}],
            "task_id": "task-1",
            "task_type": "demo",
            "feedback_value": 1,
            "timestamp": 123.4,
        }
    )

    assert payload == {
        "id": 7,
        "role": "user",
        "content": "hello",
        "images": [{"name": "chart.png"}],
        "files": [{"name": "brief.txt"}],
        "sources": [{"title": "Source A"}],
        "model_id": "qwen-main",
        "panel_id": "panel-main",
        "answer_group_id": "grp-1",
        "workflow_nodes": [{"id": "node-1"}],
        "task_id": "task-1",
        "task_type": "demo",
        "feedback_value": 1,
        "timestamp": 123.4,
    }


def test_collect_session_attachments_dedupes_and_tracks_turns():
    payload = collect_session_attachments(
        [
            {
                "timestamp": 10.0,
                "answer_group_id": "grp-1",
                "files": [
                    {
                        "name": "brief.txt",
                        "media_type": "text/plain",
                        "data_url": "data:text/plain;base64,QnJpZWY=",
                        "size_bytes": 5,
                        "extracted_text": "Alpha section\nBeta section",
                    }
                ],
                "images": [
                    {
                        "name": "chart.png",
                        "media_type": "image/png",
                        "data_url": "data:image/png;base64,ZmFrZQ==",
                    }
                ],
            },
            {
                "timestamp": 12.0,
                "answer_group_id": "grp-2",
                "files": [
                    {
                        "name": "brief.txt",
                        "media_type": "text/plain",
                        "data_url": "data:text/plain;base64,QnJpZWY=",
                        "size_bytes": 5,
                        "extracted_text": "Alpha section\nBeta section",
                    }
                ],
            },
        ],
        preview_char_limit=14,
    )

    assert payload["summary"] == {
        "total_attachments": 2,
        "file_count": 1,
        "image_count": 1,
        "text_ready_count": 1,
        "reusable_count": 2,
        "total_size_bytes": 5,
    }

    brief = next(item for item in payload["attachments"] if item["name"] == "brief.txt")
    assert brief["occurrence_count"] == 2
    assert brief["turn_count"] == 2
    assert brief["latest_answer_group_id"] == "grp-2"
    assert brief["first_seen_at"] == 10.0
    assert brief["last_seen_at"] == 12.0
    assert brief["preview_text"] == "Alpha secti..."


def test_render_shared_pages_include_expected_content():
    session_html = render_shared_session_html(
        {
            "session": {"title": "Shared Review", "updated_at": 1710000000},
            "messages": [
                {
                    "role": "user",
                    "content": "<script>alert(1)</script>",
                    "images": [
                        {
                            "name": "chart.png",
                            "data_url": "data:image/png;base64,ZmFrZQ==",
                        }
                    ],
                    "files": [{"name": "brief.txt", "extracted_text": "alpha beta gamma"}],
                    "sources": [{"title": "Source A", "snippet": "source snippet"}],
                    "model_id": "qwen-main",
                }
            ],
        },
        "http://example.test/shared/session-token",
    )

    deck = DeckSpec(
        deck_id="deck-1",
        meta=DeckMeta(
            title="Quarterly Plan",
            created_at="2026-04-11T10:00:00+0800",
            session_id="session-1",
            source_mode="kb_plus_chat",
            generator_panel_id="panel-main",
            theme="sunrise",
        ),
        generation=DeckGeneration(source="kb_plus_chat", target_slide_count=6),
        slides=[
            DeckSlide(
                id="slide-1",
                type="content",
                title="Overview",
                subtitle="Key themes",
                layout="two-column",
                speaker_notes="Line 1\nLine 2",
                quality_state="supported",
                blocks=[
                    DeckBlock(
                        id="block-1",
                        kind="bullet_list",
                        role="body",
                        content={"items": ["Point A", "Point B"]},
                    )
                ],
            )
        ],
    )
    deck_html = render_shared_deck_html(
        deck,
        "http://example.test/shared/deck-token",
    )

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in session_html
    assert "Shared Review" in session_html
    assert "brief.txt" in session_html
    assert "http://example.test/shared/session-token" in session_html

    assert "Quarterly Plan" in deck_html
    assert "主题 晨曦回顾" in deck_html
    assert "来源 知识库 + 聊天" in deck_html
    assert "Point A" in deck_html
    assert "演讲备注" in deck_html


def test_build_answer_group_review_payload_prefers_better_supported_panel(monkeypatch, tmp_path):
    import backend.chat_store as chat_store

    db_path = tmp_path / "chat_history.db"

    class TestSQLiteChatMessageHistory(chat_store.SQLiteChatMessageHistory):
        def __init__(self, session_id: str, db_path_arg: str = "./chat_history.db"):
            super().__init__(session_id=session_id, db_path=str(db_path))

    monkeypatch.setattr(chat_store, "SQLiteChatMessageHistory", TestSQLiteChatMessageHistory)

    history = TestSQLiteChatMessageHistory("session-review")
    history.add_user_message("Compare the options", answer_group_id="grp-review")
    history.add_ai_message(
        "Short answer",
        model_id="qwen-main",
        panel_id="panel-main",
        answer_group_id="grp-review",
    )
    history.add_ai_message(
        "Recommended approach:\n1. Use the supported option.\n2. Validate with evidence.\n3. Execute the rollout.",
        model_id="qwen-compare",
        panel_id="panel-compare",
        answer_group_id="grp-review",
        sources=[
            {"type": "doc", "title": "Decision Brief", "snippet": "Best option evidence"},
            {"type": "doc", "title": "Runbook", "snippet": "Execution steps"},
        ],
        workflow_nodes=[
            {"id": "classify_intent", "status": "completed"},
            {"id": "execute_tool", "status": "completed"},
        ],
        task_type="analysis",
    )
    chat_store.replace_session_panels(
        "session-review",
        [
            {
                "panel_id": "panel-main",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-main",
                "base_url": "http://localhost:11434",
                "temperature": 0.3,
                "agent_mode": "auto",
            },
            {
                "panel_id": "panel-compare",
                "provider": "ollama",
                "connection_type": "ollama",
                "model": "qwen-compare",
                "base_url": "http://localhost:11434",
                "temperature": 0.4,
                "agent_mode": "auto",
            },
        ],
        db_path=str(db_path),
    )

    payload = build_answer_group_review_payload("session-review", "grp-review")

    assert payload["recommended_panel_id"] == "panel-compare"
    assert payload["responses"][0]["panel_id"] == "panel-compare"
    assert payload["responses"][0]["source_count"] == 2
    assert payload["responses"][0]["completed_workflow_count"] == 2
    assert payload["responses"][0]["score"] > payload["responses"][1]["score"]
