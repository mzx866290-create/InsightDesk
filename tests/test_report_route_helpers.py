from types import SimpleNamespace

import pytest

from backend.helpers.report_route_helpers import create_report_artifact_result


def _request(**overrides):
    values = {
        "session_id": "session-1",
        "answer_group_id": " answer-1 ",
        "panel_id": " panel-a ",
        "template_id": "executive_report",
        "template_options": {"scope": "board", "nested": {"ignored": True}},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_create_report_artifact_result_builds_metadata_and_saves_artifact():
    saved_artifacts = []
    captured = {}

    def build_report_artifact(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(artifact_id="artifact-report-1", **kwargs)

    result = create_report_artifact_result(
        request=_request(),
        messages=["message"],
        ensure_deckable_chat=lambda messages: [("Question", "Answer")],
        build_chat_report_title=lambda messages: "Board Update",
        build_report_markdown=lambda messages, title: f"# {title}",
        build_report_artifact=build_report_artifact,
        save_artifact=saved_artifacts.append,
    )

    assert result.artifact_id == "artifact-report-1"
    assert result.title == "Board Update"
    assert result.markdown.startswith("---\ntemplate: executive_report")
    assert captured["session_id"] == "session-1"
    assert captured["answer_group_id"] == "answer-1"
    assert captured["panel_id"] == "panel-a"
    assert captured["qa_pairs"] == [("Question", "Answer")]
    assert captured["template_options"] == {"scope": "board", "nested": {"ignored": True}}
    assert saved_artifacts == [result.artifact]


def test_create_report_artifact_result_validates_template_before_building():
    build_called = False

    def build_report_artifact(**kwargs):
        nonlocal build_called
        build_called = True
        return SimpleNamespace(artifact_id="artifact-report-1")

    with pytest.raises(ValueError, match="not report"):
        create_report_artifact_result(
            request=_request(template_id="board_deck"),
            messages=["message"],
            ensure_deckable_chat=lambda messages: [("Question", "Answer")],
            build_chat_report_title=lambda messages: "Board Update",
            build_report_markdown=lambda messages, title: f"# {title}",
            build_report_artifact=build_report_artifact,
            save_artifact=lambda artifact: None,
        )

    assert build_called is False
