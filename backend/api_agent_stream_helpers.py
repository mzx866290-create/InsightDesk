import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.api_chat_stream_helpers import done_event, panel_event
from backend.api_task_store import TaskStatus

MAX_ITERATIONS_ERROR_MESSAGE = "模型工具调用次数超限，无法完成任务"
MAX_ITERATIONS_ERROR_SUGGESTION = "请尝试简化问题或切换至其他模型后重试"
MAX_ITERATIONS_DASHBOARD_ERROR = "模型工具调用次数超限，无法完成知识库仪表盘生成。"


def dashboard_prompt_excerpt(user_message: Any, limit: int = 120) -> str:
    return re.sub(r"\s+", " ", str(user_message or "").strip())[:limit]


def task_created_event(panel_id: str, task_record: Any) -> str:
    return panel_event(
        panel_id,
        "task_created",
        task_id=str(getattr(task_record, "task_id", "") or ""),
        task_type=str(getattr(task_record, "task_type", "") or ""),
    )


def stream_agent_item(panel_id: str, item: Any) -> tuple[str, str | None]:
    if isinstance(item, dict) and item.get("type") == "sources":
        return panel_event(panel_id, "sources", sources=item.get("sources", [])), None
    if isinstance(item, dict) and item.get("type") == "workflow_state":
        return (
            panel_event(
                panel_id,
                str(item.get("type") or "workflow_state"),
                **{key: value for key, value in item.items() if key != "type"},
            ),
            None,
        )

    chunk = item if isinstance(item, str) else str(item)
    return panel_event(panel_id, "chunk", content=chunk), chunk


@dataclass(frozen=True)
class NonStreamAgentOutcome:
    answer: str
    sources: list[Any]
    events: list[str]
    should_stop: bool
    dashboard_error: str | None = None


async def resolve_non_stream_agent_result(
    panel_id: str,
    result: dict[str, Any],
    *,
    mc: Any,
    message: Any,
    is_max_iterations_output: Callable[[str], bool],
    stringify_user_input: Callable[[Any], str],
    fallback_generate: Callable[[Any, str, str], Awaitable[str]],
) -> NonStreamAgentOutcome:
    answer = result.get("output", str(result))
    sources = result.get("sources", [])

    if not is_max_iterations_output(answer):
        return NonStreamAgentOutcome(
            answer=answer,
            sources=sources,
            events=[],
            should_stop=False,
        )

    intermediate = result.get("intermediate_steps", [])
    if intermediate:
        tool_outputs = "\n\n".join(str(step[1]) for step in intermediate if len(step) > 1)
        answer = await fallback_generate(
            mc,
            stringify_user_input(message),
            tool_outputs,
        )
        return NonStreamAgentOutcome(
            answer=answer,
            sources=sources,
            events=[],
            should_stop=False,
        )

    return NonStreamAgentOutcome(
        answer="",
        sources=sources,
        events=[
            panel_event(
                panel_id,
                "error",
                content=MAX_ITERATIONS_ERROR_MESSAGE,
                error_code="MAX_ITERATIONS",
                suggestion=MAX_ITERATIONS_ERROR_SUGGESTION,
            ),
            done_event(panel_id),
        ],
        should_stop=True,
        dashboard_error=MAX_ITERATIONS_DASHBOARD_ERROR,
    )


async def finalize_dashboard_task(
    task_record: Any,
    final_answer: str,
    *,
    contains_dashboard_card: Callable[[str], bool],
    summarize_dashboard_task_result: Callable[[str], str],
    summarize_dashboard_task_error: Callable[[str], str],
    set_inline_task_state: Callable[..., Awaitable[Any]],
) -> Any:
    if contains_dashboard_card(final_answer):
        return await set_inline_task_state(
            task_record,
            status=TaskStatus.COMPLETED,
            progress=100,
            result=summarize_dashboard_task_result(final_answer),
            error=None,
        )

    return await set_inline_task_state(
        task_record,
        status=TaskStatus.FAILED,
        progress=100,
        result=None,
        error=summarize_dashboard_task_error(final_answer),
    )


async def fail_dashboard_task(
    task_record: Any,
    *,
    error: str,
    set_inline_task_state: Callable[..., Awaitable[Any]],
) -> Any:
    return await set_inline_task_state(
        task_record,
        status=TaskStatus.FAILED,
        progress=100,
        result=None,
        error=error,
    )
