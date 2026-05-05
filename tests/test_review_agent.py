import asyncio

import pytest

from backend.agent import ReviewAgent, ReviewAgentConfig, apply_approval_decision


def _quality_gate(result):
    return next(item for item in result["artifacts"] if item["type"] == "quality_gate")["content"]


def _approval_recommendation(result):
    return next(
        item for item in result["artifacts"] if item["type"] == "approval_recommendation"
    )["content"]


def test_review_agent_outputs_configurable_checklist():
    agent = ReviewAgent(config=ReviewAgentConfig(checklist=["Verify cited sources", "Check numerical claims"]))

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-checklist",
                "type": "review",
                "description": "Review draft",
            },
            {
                "_agent_results": {
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nA sourced brief.",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [{"title": "Source"}],
                    }
                }
            },
        )
    )

    gate = _quality_gate(result)

    assert gate["checklist"] == [
        {"item": "Verify cited sources", "status": "configured"},
        {"item": "Check numerical claims", "status": "configured"},
    ]
    assert result["metadata"]["quality_gate"] == "pass"
    assert result["metadata"]["approval_recommendation"]["decision"] == "approve"


def test_review_agent_flags_untraced_numbers_and_dates():
    agent = ReviewAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-traceability",
                "type": "review",
                "description": "Review draft",
            },
            {
                "_agent_results": {
                    "research": {
                        "agent": "research",
                        "status": "completed",
                        "output": "Market demand increased in the latest quarter.",
                        "artifacts": [{"type": "research_report", "content": "Market demand increased."}],
                        "sources": [{"title": "Market source", "snippet": "Market demand increased."}],
                    },
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "Revenue grew 42% on 2026-04-20.",
                        "artifacts": [{"type": "markdown", "content": "Revenue grew 42% on 2026-04-20."}],
                        "sources": [{"title": "Market source"}],
                    },
                }
            },
        )
    )

    gate = _quality_gate(result)

    assert result["metadata"]["quality_gate"] == "needs_fix"
    assert result["metadata"]["passed"] is False
    assert any(issue["category"] == "evidence" for issue in gate["issues"])


def test_review_agent_flags_citations_without_sources():
    agent = ReviewAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-citations",
                "type": "review",
                "description": "Review draft",
            },
            {
                "_agent_results": {
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nThe market is expanding [1].\n\n## Sources\n- Market report",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [],
                    }
                }
            },
        )
    )

    gate = _quality_gate(result)

    assert result["metadata"]["quality_gate"] == "needs_fix"
    assert result["metadata"]["passed"] is False
    assert any(issue["category"] == "source" for issue in gate["issues"])


def test_review_agent_emits_machine_readable_approval_recommendation():
    agent = ReviewAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-approval-recommendation",
                "type": "review",
                "description": "Review missing deliverable",
            },
            {"_agent_results": {}},
        )
    )

    recommendation = _approval_recommendation(result)

    assert "## Approval Recommendation" in result["output"]
    assert recommendation == result["metadata"]["approval_recommendation"]
    assert recommendation["decision"] == "block"
    assert recommendation["gate"] == "fail"
    assert recommendation["requires_override"] is True
    assert recommendation["blocker_count"] == 1
    assert recommendation["next_actions"][0] == "Run writing, research, or data_analysis before review."
    assert "Generate a markdown delivery draft before final QA." in recommendation["next_actions"]


def test_review_agent_flags_dangling_citation_reference_map():
    agent = ReviewAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-citation-map",
                "type": "review",
                "description": "Review draft",
            },
            {
                "_agent_results": {
                    "research": {
                        "agent": "research",
                        "status": "completed",
                        "output": "Market source supports expansion.",
                        "artifacts": [{"type": "research_report", "content": "Market source supports expansion."}],
                        "sources": [{"id": "1", "title": "Market source"}],
                    },
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nThe market is expanding [2].\n\n## Sources\n1. Market source",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [],
                    },
                },
            },
        )
    )

    gate = _quality_gate(result)

    assert gate["citation_audit"]["cited_refs"] == ["2"]
    assert gate["citation_audit"]["source_section_refs"] == ["1"]
    assert result["metadata"]["quality_gate"] == "needs_fix"
    assert any("no matching source entry" in issue["message"] for issue in gate["issues"])


def test_review_agent_policy_can_require_all_source_entries_to_be_cited():
    agent = ReviewAgent(config=ReviewAgentConfig(review_policy={"allow_uncited_sources": False}))

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-policy",
                "type": "review",
                "description": "Review draft",
            },
            {
                "_agent_results": {
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nClaim [1].\n\n## Sources\n1. Used source\n2. Unused source",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [{"id": "1", "title": "Used source"}, {"id": "2", "title": "Unused source"}],
                    }
                }
            },
        )
    )

    gate = _quality_gate(result)

    assert gate["policy"]["allow_uncited_sources"] is False
    assert result["metadata"]["quality_gate"] == "pass"
    assert any("uncited references: 2" in issue["message"] for issue in gate["issues"])


def test_review_agent_policy_flags_citation_source_content_mismatch():
    agent = ReviewAgent(
        config=ReviewAgentConfig(review_policy={"enforce_citation_support_alignment": True})
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-citation-support",
                "type": "review",
                "description": "Review draft",
            },
            {
                "_agent_results": {
                    "research": {
                        "agent": "research",
                        "status": "completed",
                        "output": "Anthropic released a model safety report.",
                        "artifacts": [
                            {
                                "type": "research_report",
                                "content": "Anthropic released a model safety report.",
                            }
                        ],
                        "sources": [
                            {
                                "id": "1",
                                "title": "Anthropic safety report",
                                "snippet": "Anthropic released a model safety report.",
                            }
                        ],
                    },
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nOpenAI revenue grew rapidly [1].\n\n## Sources\n1. Anthropic safety report",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [],
                    },
                },
            },
        )
    )

    gate = _quality_gate(result)

    assert gate["policy"]["enforce_citation_support_alignment"] is True
    assert result["metadata"]["quality_gate"] == "needs_fix"
    assert any("does not appear to support" in issue["message"] for issue in gate["issues"])


def test_review_agent_policy_accepts_aligned_citation_source_content():
    agent = ReviewAgent(
        config=ReviewAgentConfig(review_policy={"enforce_citation_support_alignment": True})
    )

    result = asyncio.run(
        agent.execute(
            {
                "id": "review-citation-support-pass",
                "type": "review",
                "description": "Review draft",
            },
            {
                "_agent_results": {
                    "research": {
                        "agent": "research",
                        "status": "completed",
                        "output": "Anthropic released a model safety report.",
                        "artifacts": [
                            {
                                "type": "research_report",
                                "content": "Anthropic released a model safety report.",
                            }
                        ],
                        "sources": [
                            {
                                "id": "1",
                                "title": "Anthropic safety report",
                                "snippet": "Anthropic released a model safety report.",
                            }
                        ],
                    },
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nAnthropic released a model safety report [1].\n\n## Sources\n1. Anthropic safety report",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [],
                    },
                },
            },
        )
    )

    gate = _quality_gate(result)

    assert result["metadata"]["quality_gate"] == "pass"
    assert not any("does not appear to support" in issue["message"] for issue in gate["issues"])


def test_approval_blocks_failed_quality_gate_without_override():
    state = {
        "plan": [
            {
                "id": "publish-report",
                "agent": "integrator",
                "task_type": "publish",
                "status": "waiting_approval",
                "requires_approval": True,
                "approval_status": "pending",
            }
        ],
        "current_step": 0,
        "needs_human_approval": True,
        "approval_batch": {"step_ids": ["publish-report"]},
        "agent_results": {
            "review": {
                "agent": "review",
                "task_id": "review",
                "task_type": "review",
                "status": "completed",
                "output": "",
                "artifacts": [
                    {
                        "type": "quality_gate",
                        "content": {"gate": "fail", "passed": False, "issues": []},
                    }
                ],
                "sources": [],
            }
        },
    }

    with pytest.raises(ValueError, match="Quality gate 'fail' blocks approval"):
        apply_approval_decision(state, decision="approved", reviewer="qa")


def test_approval_records_quality_gate_when_approved():
    state = {
        "plan": [
            {
                "id": "publish-report",
                "agent": "integrator",
                "task_type": "publish",
                "status": "waiting_approval",
                "requires_approval": True,
                "approval_status": "pending",
            }
        ],
        "current_step": 0,
        "needs_human_approval": True,
        "approval_batch": {"step_ids": ["publish-report"]},
        "agent_results": {
            "review": {
                "agent": "review",
                "task_id": "review",
                "task_type": "review",
                "status": "completed",
                "output": "",
                "artifacts": [
                    {
                        "type": "quality_gate",
                        "content": {"gate": "pass", "passed": True, "issues": []},
                    }
                ],
                "sources": [],
            }
        },
    }

    next_state = apply_approval_decision(state, decision="approved", reviewer="qa")

    approval = next_state["plan"][0]["metadata"]["approval"]
    assert approval["quality_gate"]["gate"] == "pass"
    assert approval["policy"]["block_on_quality_gates"] == ["fail"]


def test_approval_blocks_review_request_changes_recommendation_without_override():
    review_result = asyncio.run(
        ReviewAgent().execute(
            {
                "id": "review-request-changes",
                "type": "review",
                "description": "Review draft with dangling citation",
            },
            {
                "_agent_results": {
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nRevenue grew 42% [1].\n\n## Sources\n- Source pending",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [],
                    }
                }
            },
        )
    )
    recommendation = _approval_recommendation(review_result)
    state = {
        "plan": [
            {
                "id": "publish-report",
                "agent": "integrator",
                "task_type": "publish",
                "status": "waiting_approval",
                "requires_approval": True,
                "approval_status": "pending",
            }
        ],
        "current_step": 0,
        "needs_human_approval": True,
        "approval_batch": {"step_ids": ["publish-report"]},
        "agent_results": {"review": review_result},
    }

    assert recommendation["decision"] == "request_changes"
    assert recommendation["gate"] == "needs_fix"
    with pytest.raises(ValueError, match="Review recommendation 'request_changes' blocks approval"):
        apply_approval_decision(state, decision="approved", reviewer="qa")


def test_approval_override_records_review_recommendation_metadata():
    review_result = asyncio.run(
        ReviewAgent().execute(
            {
                "id": "review-override",
                "type": "review",
                "description": "Review draft with dangling citation",
            },
            {
                "_agent_results": {
                    "writing": {
                        "agent": "writing",
                        "status": "completed",
                        "output": "# Draft\n\nRevenue grew 42% [1].\n\n## Sources\n- Source pending",
                        "artifacts": [{"type": "markdown", "content": "# Draft"}],
                        "sources": [],
                    }
                }
            },
        )
    )
    state = {
        "plan": [
            {
                "id": "publish-report",
                "agent": "integrator",
                "task_type": "publish",
                "status": "waiting_approval",
                "requires_approval": True,
                "approval_status": "pending",
                "metadata": {
                    "approval_policy": {
                        "block_on_quality_gates": ["fail"],
                        "allow_quality_gate_override": True,
                    }
                },
            }
        ],
        "current_step": 0,
        "needs_human_approval": True,
        "approval_batch": {"step_ids": ["publish-report"]},
        "agent_results": {"review": review_result},
    }

    next_state = apply_approval_decision(
        state,
        decision="approved",
        reviewer="owner",
        comment="Accepting citation cleanup as a tracked follow-up.",
    )

    approval = next_state["plan"][0]["metadata"]["approval"]
    assert approval["quality_gate"]["gate"] == "needs_fix"
    assert approval["review"]["approval_recommendation"]["decision"] == "request_changes"
    assert approval["policy"]["allow_quality_gate_override"] is True
