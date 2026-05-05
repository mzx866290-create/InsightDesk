from backend.helpers.session_memory_helpers import (
    build_phase_summary_content,
    build_phase_summary_llm_prompt,
    covered_turns_from_summary,
    latest_auto_summary,
    normalize_llm_text_content,
    summarize_window_meta,
    summary_turns,
)


def _clip_text(text, limit):
    text = " ".join(str(text).strip().split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 3)].rstrip() + "..."


def test_normalize_llm_text_content_supports_string_and_blocks():
    assert normalize_llm_text_content(" hello ") == "hello"
    assert normalize_llm_text_content(
        [{"text": "第一行"}, {"text": "第二行"}, "补充"]
    ) == "第一行\n第二行\n补充"


def test_build_phase_summary_llm_prompt_and_summary_turns():
    turns = summary_turns(
        [
            {"id": 1, "type": "human", "content": " 用户目标一 "},
            {"id": 2, "type": "ai", "content": " 助手进展一 "},
            {"id": 3, "type": "system", "content": "ignore"},
        ],
        clip_text=_clip_text,
    )

    prompt = build_phase_summary_llm_prompt(turns, total_turns=2)

    assert turns == [
        {"id": 1, "type": "human", "content": "用户目标一"},
        {"id": 2, "type": "ai", "content": "助手进展一"},
    ]
    assert "Session total human/assistant turns: 2" in prompt
    assert "1. USER: 用户目标一" in prompt
    assert "2. ASSISTANT: 助手进展一" in prompt


def test_build_phase_summary_content_and_summary_meta():
    turns = [
        {"id": 11, "type": "human", "content": "整理预算复盘"},
        {"id": 12, "type": "ai", "content": "已汇总关键指标"},
        {"id": 13, "type": "human", "content": "继续补风险项"},
    ]

    content = build_phase_summary_content(
        turns,
        total_turns=18,
        clip_text=_clip_text,
        max_chars=500,
    )
    meta = summarize_window_meta(
        total_turns=18,
        trigger="manual_api",
        generator="rules",
        window_turns=turns,
    )

    assert "latest 3 turns" in content
    assert "User focus: 整理预算复盘 | 继续补风险项" in content
    assert "Assistant progress: 已汇总关键指标" in content
    assert meta == {
        "source": "auto",
        "trigger": "manual_api",
        "generator": "rules",
        "message_coverage": 18,
        "window_size": 3,
        "window_start_id": 11,
        "window_end_id": 13,
        "version": "v1",
    }


def test_latest_auto_summary_and_covered_turns():
    summaries = [
        {"id": "manual", "meta": {"source": "manual", "message_coverage": 3}},
        {"id": "auto", "meta": {"source": "auto", "message_coverage": 12}},
    ]

    latest = latest_auto_summary(summaries)

    assert latest["id"] == "auto"
    assert covered_turns_from_summary(latest) == 12
    assert covered_turns_from_summary({"meta": {"message_coverage": "bad"}}) == 0
    assert covered_turns_from_summary(None) == 0
