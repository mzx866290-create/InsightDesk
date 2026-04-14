import asyncio
import json
import re
from types import SimpleNamespace

import agent_core


def _extract_card_payload(output: str) -> dict:
    match = re.search(r":::dashboard-card\s*\n([\s\S]*?)\n:::", output)
    assert match is not None
    return json.loads(match.group(1))


def test_extract_attachment_evidence_preserves_attachment_titles():
    user_input = (
        "请根据附件生成仪表盘\n\n"
        f"{agent_core.CHAT_FILE_CONTEXT_START_MARKER}\n"
        "[附件 1]\n"
        "文件名：dashboard_template_v1.xlsx\n"
        "内容：\n"
        "【Sheet:业务销售看板】\n"
        "行1: 日期: 2026-04-01 | 区域: 华北 | 销售额(CNY): 12500 | 订单量: 135\n"
        "[附件 2]\n"
        "文件名：notes.txt\n"
        "内容：\n"
        "这里是补充说明\n"
        f"{agent_core.CHAT_FILE_CONTEXT_END_MARKER}"
    )

    evidence = agent_core._extract_attachment_evidence(user_input)

    assert [item["title"] for item in evidence] == [
        "dashboard_template_v1.xlsx",
        "notes.txt",
    ]
    assert evidence[0]["source_type"] == "attachment"
    assert "业务销售看板" in evidence[0]["snippet"]


def test_generate_dashboard_from_attachment_falls_back_to_table_card_on_invalid_json(monkeypatch):
    async def fake_invoke(llm, prompt, timeout_seconds=None):
        del llm, prompt, timeout_seconds
        return SimpleNamespace(content="not-json")

    monkeypatch.setattr(agent_core, "_ainvoke_llm_with_timeout", fake_invoke)

    user_input = (
        "请根据附件生成仪表盘\n\n"
        f"{agent_core.CHAT_FILE_CONTEXT_START_MARKER}\n"
        "[附件 1]\n"
        "文件名：dashboard_template_v1.xlsx\n"
        "内容：\n"
        "【Sheet:业务销售看板】\n"
        "行1: 日期: 2026-04-01 | 区域: 华北 | 产品类别: 智能硬件 | 访问量: 4500 | 订单量: 135 | 销售额(CNY): 12500 | 转化率: 0.03\n"
        "行2: 日期: 2026-04-02 | 区域: 华东 | 产品类别: 家用电器 | 访问量: 5200 | 订单量: 149 | 销售额(CNY): 13800 | 转化率: 0.028\n"
        f"{agent_core.CHAT_FILE_CONTEXT_END_MARKER}"
    )
    evidence = agent_core._extract_attachment_evidence(user_input)

    result = asyncio.run(
        agent_core._generate_dashboard_from_attachment(
            object(),
            user_input,
            evidence,
            dashboard_template={"title_hint": "销售看板"},
        )
    )

    assert ":::dashboard-card" in result["output"]
    assert result["sources"][0]["title"] == "dashboard_template_v1.xlsx"

    payload = _extract_card_payload(result["output"])
    assert payload["title"] == "销售看板"
    assert payload["table"]["columns"][:4] == ["日期", "区域", "产品类别", "访问量"]
    assert payload["metrics"][0]["label"] == "销售额(CNY)"
    assert payload["charts"][0]["chart_data"]["labels"] == ["2026-04-01", "2026-04-02"]
    assert payload["evidence"][0]["title"] == "dashboard_template_v1.xlsx"


def test_generate_dashboard_from_attachment_accepts_table_only_model_payload(monkeypatch):
    async def fake_invoke(llm, prompt, timeout_seconds=None):
        del llm, prompt, timeout_seconds
        return SimpleNamespace(
            content=json.dumps(
                {
                    "title": "附件表格看板",
                    "summary": "仅保留表格明细",
                    "metrics": [],
                    "charts": [],
                    "table": {
                        "title": "数据明细",
                        "columns": ["区域", "销售额(CNY)"],
                        "rows": [{"区域": "华北", "销售额(CNY)": 12500}],
                        "evidence_ids": ["a1"],
                    },
                    "evidence": [],
                    "warnings": [],
                },
                ensure_ascii=False,
            )
        )

    monkeypatch.setattr(agent_core, "_ainvoke_llm_with_timeout", fake_invoke)

    user_input = (
        "请根据附件生成仪表盘\n\n"
        f"{agent_core.CHAT_FILE_CONTEXT_START_MARKER}\n"
        "[附件 1]\n"
        "文件名：dashboard_template_v1.xlsx\n"
        "内容：\n"
        "【Sheet:业务销售看板】\n"
        "行1: 区域: 华北 | 销售额(CNY): 12500\n"
        f"{agent_core.CHAT_FILE_CONTEXT_END_MARKER}"
    )
    evidence = agent_core._extract_attachment_evidence(user_input)

    result = asyncio.run(
        agent_core._generate_dashboard_from_attachment(
            object(),
            user_input,
            evidence,
        )
    )

    payload = _extract_card_payload(result["output"])
    assert payload["title"] == "附件表格看板"
    assert payload["table"]["rows"][0]["销售额(CNY)"] == 12500


def test_generate_dashboard_from_attachment_keeps_error_when_no_tabular_fallback(monkeypatch):
    async def fake_invoke(llm, prompt, timeout_seconds=None):
        del llm, prompt, timeout_seconds
        return SimpleNamespace(content="not-json")

    monkeypatch.setattr(agent_core, "_ainvoke_llm_with_timeout", fake_invoke)

    user_input = (
        "请根据附件生成仪表盘\n\n"
        f"{agent_core.CHAT_FILE_CONTEXT_START_MARKER}\n"
        "[附件 1]\n"
        "文件名：notes.txt\n"
        "内容：\n"
        "这是一个偏描述性的项目总结，没有稳定的表格结构。\n"
        f"{agent_core.CHAT_FILE_CONTEXT_END_MARKER}"
    )
    evidence = agent_core._extract_attachment_evidence(user_input)

    result = asyncio.run(
        agent_core._generate_dashboard_from_attachment(
            object(),
            user_input,
            evidence,
        )
    )

    assert "结构化整理过程失败" in result["output"]
    assert ":::dashboard-card" not in result["output"]
