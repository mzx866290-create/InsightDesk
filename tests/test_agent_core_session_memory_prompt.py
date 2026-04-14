from langchain_core.messages import SystemMessage

from agent_core import _build_session_memory_message


def test_session_memory_prompt_distinguishes_auto_summary_and_manual_items():
    message = _build_session_memory_message(
        [
            {
                "id": "m1",
                "kind": "fact",
                "content": "用户希望输出保持中文。",
                "created_at": 1,
                "updated_at": 1,
                "meta": {"source": "manual"},
            },
            {
                "id": "m2",
                "kind": "summary",
                "content": "当前阶段目标是收敛发布方案，并确认预算约束。",
                "created_at": 2,
                "updated_at": 2,
                "meta": {"source": "auto"},
            },
            {
                "id": "m3",
                "kind": "decision",
                "content": "优先修复稳定性和搜索问题，再做界面扩展。",
                "created_at": 3,
                "updated_at": 3,
                "meta": {"source": "manual"},
            },
            {
                "id": "m4",
                "kind": "todo",
                "content": "补齐回归测试并验证请求链路日志。",
                "created_at": 4,
                "updated_at": 4,
                "meta": {"source": "manual"},
            },
        ]
    )

    assert isinstance(message, SystemMessage)
    assert "自动阶段摘要" in message.content
    assert "已确认决策" in message.content
    assert "后续待办" in message.content
    assert "长期记忆" in message.content

