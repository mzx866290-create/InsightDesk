import asyncio

from backend.agent.agents.data_analysis import DataAnalysisAgent


def test_data_analysis_agent_applies_nested_structured_filter_tree_from_task_metadata():
    filter_tree = {
        "logic": "and",
        "conditions": [
            {"column": "region", "operator": "in", "value": ["North", "South"]},
            {
                "logic": "or",
                "conditions": [
                    {"column": "channel", "operator": "=", "value": "online"},
                    {"column": "revenue", "operator": ">=", "value": 150},
                ],
            },
        ],
    }
    agent = DataAnalysisAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "data-1",
                "type": "data_analysis",
                "description": "Rank revenue by region",
                "input": "top regions by revenue",
                "metadata": {
                    "rows": [
                        {"region": "North", "channel": "online", "revenue": 120},
                        {"region": "North", "channel": "retail", "revenue": 160},
                        {"region": "South", "channel": "retail", "revenue": 200},
                        {"region": "South", "channel": "partner", "revenue": 140},
                        {"region": "East", "channel": "online", "revenue": 300},
                    ],
                    "query": {
                        "intent": "top",
                        "metric": "revenue",
                        "dimension": "region",
                        "limit": 5,
                        "filter_tree": filter_tree,
                    },
                },
            },
            {},
        )
    )

    query_result = next(item["content"] for item in result["artifacts"] if item["type"] == "query_result")

    assert query_result["filter_tree"] == filter_tree
    assert query_result["filter_groups"] == [
        [
            {"column": "region", "operator": "in", "value": ["North", "South"]},
            {"column": "channel", "operator": "=", "value": "online"},
        ],
        [
            {"column": "region", "operator": "in", "value": ["North", "South"]},
            {"column": "revenue", "operator": ">=", "value": 150},
        ],
    ]
    assert [row["dimension"] for row in query_result["rows"]] == ["North", "South"]
    assert [row["value"] for row in query_result["rows"]] == [280.0, 200.0]
    assert result["metadata"]["query_config_source"] == "task.metadata.query"
    assert result["metadata"]["applied_filter_tree"] == filter_tree


def test_data_analysis_agent_reports_sampling_config_metadata_from_context():
    agent = DataAnalysisAgent()

    result = asyncio.run(
        agent.execute(
            {
                "id": "data-2",
                "type": "data_analysis",
                "description": "Analyze sampled workbook rows",
                "input": "analyze workbook rows",
            },
            {
                "rows": [{"region": "North", "revenue": 120}, {"region": "South", "revenue": 180}],
                "data_sampling_config": {
                    "sampled": True,
                    "row_count": 1200,
                    "sampled_row_count": 300,
                    "sample_limit": 300,
                    "sheet_name": "Revenue",
                    "sheet_index": 1,
                },
            },
        )
    )

    profile = next(item["content"] for item in result["artifacts"] if item["type"] == "json")

    assert "Sampling: showing 300 of 1200 parsed rows" in result["output"]
    assert profile["sampling"]["sample_limit"] == 300
    assert result["metadata"]["sampling"] == {
        "sampled": True,
        "row_count": 1200,
        "sampled_row_count": 300,
        "sample_limit": 300,
        "sheet_name": "Revenue",
        "sheet_index": 1,
    }
