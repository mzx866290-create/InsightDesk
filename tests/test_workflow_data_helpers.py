import base64

from backend.helpers.workflow_data_helpers import (
    decode_workflow_data_url,
    enrich_workflow_data_context,
    ensure_data_analysis_plan_step,
)


def test_decode_workflow_data_url_accepts_base64_and_urlencoded_payloads():
    encoded = base64.b64encode(b"city,revenue\nShanghai,10").decode("ascii")

    assert decode_workflow_data_url(f"data:text/csv;base64,{encoded}") == (
        b"city,revenue\nShanghai,10"
    )
    assert decode_workflow_data_url("data:text/csv,city%2Crevenue%0AShanghai%2C10") == (
        b"city,revenue\nShanghai,10"
    )
    assert decode_workflow_data_url("not-a-data-url") == b""


def test_enrich_workflow_data_context_extracts_rows_and_sampling_metadata():
    rows = "\n".join(f"{index},value-{index}" for index in range(5))

    context, summaries = enrich_workflow_data_context(
        {"topic": "sales"},
        [
            {
                "name": "sample.csv",
                "extracted_text": f"id,name\n{rows}",
            }
        ],
        row_sample_limit=2,
    )

    assert summaries == [
        {
            "name": "sample.csv",
            "row_count": 5,
            "sampled": True,
            "sampled_row_count": 2,
            "sample_limit": 2,
        }
    ]
    assert context["topic"] == "sales"
    assert context["data_source"] == "sample.csv"
    assert context["data_files"] == summaries
    assert context["data_sampling"] == summaries[0]
    assert len(context["rows"]) == 2


def test_ensure_data_analysis_plan_step_inserts_before_writing_steps():
    plan = [{"agent": "research"}, {"agent": "writing", "id": "write"}]

    next_plan = ensure_data_analysis_plan_step(
        plan,
        user_request="Analyze the uploaded data",
        has_data_rows=True,
    )

    assert [step["agent"] for step in next_plan] == [
        "research",
        "data_analysis",
        "writing",
    ]
    assert next_plan[1]["metadata"] == {"planner": "workflow_data_files"}
    assert plan == [{"agent": "research"}, {"agent": "writing", "id": "write"}]


def test_ensure_data_analysis_plan_step_keeps_existing_data_analysis_step():
    plan = [{"agent": "data_analysis", "id": "existing"}]

    assert (
        ensure_data_analysis_plan_step(
            plan,
            user_request="Analyze the uploaded data",
            has_data_rows=True,
        )
        is plan
    )
