"""History loading and persistence helpers for agent builder wrappers."""

from typing import Any, Optional

from langchain_core.messages import BaseMessage

from backend.agent.builder_context import BuilderInvocationConfig
import backend.agent.runtime_support as runtime_support


def _load_chat_history(
    session_id: str,
    panel_id: str = "",
    exclude_ai_answer_group_id: str = "",
    omit_history: bool = False,
) -> list[BaseMessage]:
    if omit_history:
        # Clear-context mode: skip both persisted messages and session memory for this call only.
        return []

    history = runtime_support.create_chat_message_history(session_id=session_id)
    session_memory = runtime_support.list_session_memory(
        session_id,
        limit=10,
        db_path=history.db_path,
    )
    memory_message = runtime_support._build_session_memory_message(session_memory)
    if panel_id and exclude_ai_answer_group_id:
        chat_history = list(
            history.get_panel_messages_for_rerun(
                panel_id,
                exclude_ai_answer_group_id,
            )
        )
    elif panel_id:
        chat_history = list(history.get_panel_messages(panel_id))
    else:
        chat_history = list(history.messages)

    if memory_message is not None:
        return [memory_message, *chat_history]
    return chat_history


def _persist_panel_history(
    session_id: str,
    user_input: Any,
    output: str,
    *,
    panel_id: str = "",
    model_id: str = "",
    answer_group_id: str = "",
    persist_user_history: bool = True,
    persist_ai_history: bool = True,
    replace_ai_history: bool = False,
    raw_user_message: str = "",
    raw_images: Optional[list[dict[str, Any]]] = None,
    raw_files: Optional[list[dict[str, Any]]] = None,
    sources: Optional[list[dict[str, Any]]] = None,
    workflow_nodes: Optional[list[dict[str, Any]]] = None,
    task_id: str = "",
    task_type: str = "",
    token_usage: Optional[dict[str, Any]] = None,
) -> None:
    history = runtime_support.create_chat_message_history(session_id=session_id)
    summarized_input = runtime_support._summarize_user_input_for_history(user_input)
    display_input = str(raw_user_message or "").strip()
    cleaned_output = runtime_support._strip_think_tags(output)
    if answer_group_id and (persist_user_history or persist_ai_history):
        history.add_user_message_once(
            display_input or summarized_input,
            answer_group_id=answer_group_id,
            images=raw_images or [],
            files=raw_files or [],
        )
    elif persist_user_history:
        history.add_user_message(
            display_input or summarized_input,
            images=raw_images or [],
            files=raw_files or [],
        )
    if persist_ai_history and cleaned_output.strip():
        if replace_ai_history and answer_group_id and panel_id:
            history.delete_ai_messages_for_answer_group(panel_id, answer_group_id)
        history.add_ai_message(
            cleaned_output,
            model_id=model_id,
            panel_id=panel_id,
            answer_group_id=answer_group_id,
            sources=sources or [],
            workflow_nodes=workflow_nodes or [],
            task_id=task_id,
            task_type=task_type,
            token_usage=token_usage or {},
        )


def _persist_output_history(
    invocation: BuilderInvocationConfig,
    user_input: Any,
    output: str,
    *,
    sources: Optional[list[dict[str, Any]]] = None,
    workflow_nodes: Optional[list[dict[str, Any]]] = None,
    task_id: str = "",
    task_type: str = "",
    token_usage: Optional[dict[str, Any]] = None,
) -> None:
    if not invocation.should_persist_history:
        return
    _persist_panel_history(
        invocation.session_id,
        user_input,
        output,
        panel_id=invocation.panel_id,
        model_id=invocation.model_id,
        answer_group_id=invocation.answer_group_id,
        persist_user_history=invocation.persist_user_history,
        persist_ai_history=invocation.persist_ai_history,
        replace_ai_history=invocation.replace_ai_history,
        raw_user_message=invocation.raw_user_message,
        raw_images=invocation.raw_images,
        raw_files=invocation.raw_files,
        sources=sources or [],
        workflow_nodes=workflow_nodes or [],
        task_id=task_id or invocation.task_id,
        task_type=task_type or invocation.task_type,
        token_usage=token_usage or {},
    )


def _persist_agent_result_history(
    invocation: BuilderInvocationConfig,
    user_input: Any,
    result: dict[str, Any],
) -> None:
    _persist_output_history(
        invocation,
        user_input,
        str(result.get("output", "") or ""),
        sources=result.get("sources", []),
        workflow_nodes=result.get("workflow_nodes", []),
        task_id=str(result.get("task_id", "") or ""),
        task_type=str(result.get("task_type", "") or ""),
        token_usage=dict(result.get("token_usage") or {}),
    )
