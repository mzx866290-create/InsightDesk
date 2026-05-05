import asyncio

from backend.agent.agents.writer import WritingAgent


def _context() -> dict:
    return {
        "_agent_results": {
            "research-step": {
                "agent": "research",
                "status": "completed",
                "output": "Research Agent findings",
                "artifacts": [
                    {
                        "type": "research_report",
                        "summary": "Market demand is expanding.",
                        "highlights": ["Enterprise adoption is increasing."],
                        "caveats": ["Validate regional estimates."],
                    }
                ],
                "sources": [{"title": "Market source", "url": "https://example.test/source"}],
            },
            "data-step": {
                "agent": "data_analysis",
                "status": "completed",
                "output": "Data Agent Analysis",
                "artifacts": [
                    {
                        "type": "json",
                        "content": {
                            "row_count": 4,
                            "column_count": 3,
                            "numeric_columns": {
                                "revenue": {
                                    "sum": 800,
                                    "mean": 200,
                                    "min": 150,
                                    "max": 250,
                                }
                            },
                        },
                    }
                ],
                "sources": [{"type": "dataset", "title": "pipeline.csv"}],
            },
        }
    }


def test_writing_agent_default_template_keeps_legacy_heading():
    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-default",
                "type": "writing",
                "input": "Create a delivery brief",
            },
            _context(),
        )
    )

    assert "# Writing Agent Draft" in result["output"]
    assert "## Executive Summary" in result["output"]
    assert "Enterprise adoption is increasing." in result["output"]
    assert result["metadata"]["template"] == "default"
    assert result["metadata"]["style"] == "default"
    assert "Executive Summary" in result["metadata"]["template_sections"]
    assert [artifact["type"] for artifact in result["artifacts"]] == ["markdown"]
    assert "deck_json_generated" not in result["metadata"]


def test_writing_agent_uses_template_from_task_metadata():
    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-exec",
                "type": "writing",
                "input": "Summarize the launch decision",
                "metadata": {"template": "executive_brief"},
            },
            _context(),
        )
    )

    assert "# Executive Brief Draft" in result["output"]
    assert "## Bottom Line" in result["output"]
    assert "## Data Snapshot" in result["output"]
    assert "Enterprise adoption is increasing." in result["output"]
    assert "Dataset profile: 4 rows across 3 columns." in result["output"]
    assert result["metadata"]["template"] == "executive_brief"
    assert result["metadata"]["style"] == "executive"
    assert result["metadata"]["template_sections"] == [
        "Request",
        "Bottom Line",
        "Key Signals",
        "Data Snapshot",
        "Evidence",
        "Risks And Next Steps",
    ]


def test_writing_agent_uses_template_from_context():
    context = _context()
    context["writing_style"] = "decision_memo"

    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-decision",
                "type": "writing",
                "input": "Decide whether to expand the pilot",
            },
            context,
        )
    )

    assert "# Decision Memo Draft" in result["output"]
    assert "## Recommendation" in result["output"]
    assert "## Data Considerations" in result["output"]
    assert "Market source" in result["output"]
    assert result["metadata"]["template"] == "decision_memo"
    assert result["metadata"]["style"] == "decision"
    assert "Recommendation" in result["metadata"]["template_sections"]


def test_writing_agent_generates_deck_json_from_task_metadata():
    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-deck",
                "type": "writing",
                "input": "Create a board-ready deck",
                "metadata": {"output_format": "deck_json", "template": "executive_brief"},
            },
            _context(),
        )
    )

    deck_artifacts = [artifact for artifact in result["artifacts"] if artifact["type"] == "deck_json"]
    assert len(deck_artifacts) == 1
    deck = deck_artifacts[0]["content"]
    assert result["output"].startswith("# Executive Brief Draft")
    assert deck["version"] == "1.0"
    assert deck["title"] == "Create a board-ready deck"
    assert deck["generation"] == {
        "source": "writing_agent",
        "template": "executive_brief",
        "style": "executive",
    }
    assert deck["source_registry"] == [
        {
            "id": "src-1",
            "agent": "research",
            "title": "Market source",
            "url": "https://example.test/source",
            "type": "",
        },
        {
            "id": "src-2",
            "agent": "data_analysis",
            "title": "pipeline.csv",
            "url": "",
            "type": "dataset",
        },
    ]
    assert deck["slides"][0] == {
        "id": "slide-1",
        "type": "title",
        "title": "Create a board-ready deck",
        "blocks": [
            {
                "type": "text",
                "text": "This draft combines upstream research findings with structured data-analysis artifacts.",
            }
        ],
        "evidence_refs": ["src-1", "src-2"],
        "quality_state": "draft",
    }
    assert any(slide["title"] == "Data Highlights" for slide in deck["slides"])
    assert all(slide["quality_state"] == "draft" for slide in deck["slides"])
    assert result["metadata"]["deck_json_generated"] is True
    assert result["metadata"]["deck_slide_count"] == len(deck["slides"])


def test_writing_agent_generates_minimal_deck_json_from_context_request():
    context = {"delivery_format": "deck"}

    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-minimal-deck",
                "type": "writing",
                "input": "Plan the next update",
            },
            context,
        )
    )

    deck = next(artifact["content"] for artifact in result["artifacts"] if artifact["type"] == "deck_json")
    assert deck["slides"][0]["type"] == "title"
    assert deck["slides"][1]["title"] == "Summary"
    assert deck["slides"][-1]["title"] == "Next Steps"
    assert deck["source_registry"] == []
    assert result["metadata"]["deck_json_generated"] is True
    assert result["metadata"]["deck_slide_count"] == 3


def test_writing_agent_negotiates_custom_outline_with_template_sections():
    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-outline",
                "type": "writing",
                "input": "Draft a launch narrative",
                "metadata": {
                    "template": "executive_brief",
                    "outline_sections": ["Audience", "Recommendation", "Risks And Next Steps"],
                },
            },
            _context(),
        )
    )

    agreement = result["metadata"]["outline_agreement"]
    assert "## Outline Agreement" in result["output"]
    assert agreement["status"] == "merged"
    assert agreement["requested_sections"] == ["Audience", "Recommendation", "Risks And Next Steps"]
    assert agreement["selected_sections"][:3] == ["Audience", "Recommendation", "Risks And Next Steps"]
    assert "Bottom Line" in agreement["added_sections"]
    assert "Added sections:" in result["output"]
    assert result["output"].index("## Audience") < result["output"].index("## Recommendation")
    assert result["output"].index("## Recommendation") < result["output"].index("## Risks And Next Steps")
    assert "- Audience inferred from request: Draft a launch narrative" in result["output"]


def test_writing_agent_fact_check_loop_flags_claims_without_sources():
    context = {
        "_agent_results": {
            "research-step": {
                "agent": "research",
                "status": "completed",
                "output": "Research Agent findings",
                "artifacts": [
                    {
                        "type": "research_report",
                        "summary": "Retention improved by 20 percent.",
                        "highlights": ["Expansion revenue doubled."],
                    }
                ],
                "sources": [],
            }
        }
    }

    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-fact-check",
                "type": "writing",
                "input": "Write a sourced update",
            },
            context,
        )
    )

    fact_check = result["metadata"]["fact_check"]
    assert "## Fact Check" in result["output"]
    assert fact_check["summary"] == "2 of 2 claims need source confirmation."
    assert [claim["status"] for claim in fact_check["claims"]] == ["needs_source", "needs_source"]
    assert "Confirm source support before publishing: Retention improved by 20 percent." in result["output"]


def test_writing_agent_style_correction_loop_trims_executive_bullets():
    context = {
        "_agent_results": {
            "research-step": {
                "agent": "research",
                "status": "completed",
                "output": "Research Agent findings",
                "artifacts": [
                    {
                        "type": "research_report",
                        "highlights": [
                            "Enterprise teams need a highly detailed migration narrative that explains readiness, "
                            "dependency timing, enablement work, operational ownership, and measurable executive "
                            "review criteria across every launch workstream."
                        ],
                    }
                ],
                "sources": [{"title": "Readiness report"}],
            }
        }
    }

    result = asyncio.run(
        WritingAgent().execute(
            {
                "id": "write-style",
                "type": "writing",
                "input": "Prepare an executive update",
                "metadata": {"template": "executive_brief"},
            },
            context,
        )
    )

    correction = result["metadata"]["style_correction"]
    assert correction == {
        "status": "corrected",
        "style": "executive",
        "changes": ["trimmed_executive_bullets"],
    }
    assert any(line.endswith("...") for line in result["output"].splitlines() if line.startswith("- "))
