from backend.agent.agents.model_compare import build_evaluation_repository, synthesize_model_comparison


def test_evaluation_repository_applies_preferred_model_id_bonus():
    repository = build_evaluation_repository(
        [
            {
                "panel_id": "panel-a",
                "model_id": "model-a",
                "content": "Longer answer with enough detail to win without an explicit model preference.",
                "sources": [{"title": "Source"}],
            },
            {
                "panel_id": "panel-b",
                "model_id": "model-b",
                "content": "Short answer.",
                "sources": [],
            },
        ],
        weights={
            "source_count": 0.0,
            "artifact_count": 0.0,
            "completed_workflow_count": 0.0,
            "content_depth": 0.001,
            "preference_bonus": 10.0,
        },
        preferred_model_id="model-b",
    )

    preference = repository["preference_model"]

    assert repository["ranking"][0]["model_id"] == "model-b"
    assert preference["preferred_model_id"] == "model-b"
    assert preference["selected_model_id"] == "model-b"


def test_evaluation_repository_exposes_reusable_evaluation_matrix():
    repository = build_evaluation_repository(
        [
            {
                "panel_id": "panel-a",
                "model_id": "model-a",
                "content": "Sourced implementation plan",
                "sources": [{"title": "Runbook"}],
                "artifacts": [{"type": "plan"}],
                "metadata": {"completed_workflow_count": 2},
            },
            {
                "panel_id": "panel-b",
                "model_id": "model-b",
                "content": "Short note",
                "sources": [],
            },
        ]
    )

    matrix = repository["evaluation_matrix"]

    assert matrix[0]["rank"] == 1
    assert matrix[0]["panel_id"] == repository["ranking"][0]["panel_id"]
    assert matrix[0]["criteria"]["source_count"]["value"] == 1
    assert matrix[0]["criteria"]["artifact_count"]["value"] == 1
    assert matrix[0]["criteria"]["completed_workflow_count"]["value"] == 2
    assert repository["preference_model"]["selected_score"] == repository["ranking"][0]["score"]


def test_evaluation_repository_enforces_required_preference_contract_terms():
    repository = build_evaluation_repository(
        [
            {
                "panel_id": "panel-a",
                "model_id": "model-a",
                "content": "Long sourced answer with architecture detail but no contract language.",
                "sources": [{"title": "Source A"}, {"title": "Source B"}],
            },
            {
                "panel_id": "panel-b",
                "model_id": "model-b",
                "content": "Implementation uses a typed contract and regression tests.",
                "sources": [],
            },
        ],
        preference_contract={
            "required_terms": ["typed contract"],
            "preferred_terms": ["regression tests"],
            "avoid_terms": ["external api"],
        },
    )

    ranking = repository["ranking"]
    matrix = repository["evaluation_matrix"]
    preference = repository["preference_model"]

    assert ranking[0]["panel_id"] == "panel-b"
    assert ranking[0]["contract_evaluation"]["contract_satisfied"] is True
    assert ranking[1]["contract_evaluation"]["missing_required_terms"] == ["typed contract"]
    assert preference["selected_contract_satisfied"] is True
    assert preference["selected_missing_required_terms"] == []
    assert preference["preference_contract"]["required_terms"] == ["typed contract"]
    assert matrix[0]["criteria"]["required_term_coverage"]["value"] == 1.0
    assert matrix[0]["criteria"]["required_term_coverage"]["matched_terms"] == ["typed contract"]
    assert matrix[0]["criteria"]["preferred_term_match"]["matched_terms"] == ["regression tests"]
    assert "satisfies preference contract" in repository["comparisons"][0]["winner_advantages"]


def test_model_compare_synthesis_records_source_input_audit():
    repository = build_evaluation_repository(
        [
            {
                "panel_id": "panel-a",
                "model_id": "model-a",
                "content": "Detailed answer about evidence reuse and regression testing.",
                "sources": [{"title": "Runbook"}],
            },
            {
                "panel_id": "panel-b",
                "model_id": "model-b",
                "content": "Alternative answer with rollout notes.",
            },
        ],
        preference_contract={"required_terms": ["evidence reuse"], "preferred_terms": ["regression testing"]},
    )

    synthesis = synthesize_model_comparison(repository, user_request="Compare plans")

    assert synthesis["merged_candidate_count"] == 2
    assert synthesis["source_panel_ids"] == [
        item["panel_id"] for item in synthesis["synthesis_inputs"]
    ]
    assert synthesis["synthesis_inputs"][0]["rank"] == 1
    assert synthesis["synthesis_inputs"][0]["contract_satisfied"] is True
    assert synthesis["synthesis_inputs"][0]["excerpt"]
    assert synthesis["preference_contract"]["required_terms"] == ["evidence reuse"]
    assert synthesis["selection_reasons"][0] == "satisfied required terms: evidence reuse"
    assert "Selected because:" in synthesis["answer"]
