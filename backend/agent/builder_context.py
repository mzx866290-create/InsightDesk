"""Small pure helpers shared by agent builder wrappers."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class BuilderInvocationConfig:
    session_id: Any
    persist_history: bool
    panel_id: str
    model_id: str
    answer_group_id: str
    exclude_ai_answer_group_id: str
    persist_user_history: bool
    persist_ai_history: bool
    replace_ai_history: bool
    raw_user_message: str
    raw_images: list[dict[str, Any]]
    raw_files: list[dict[str, Any]]
    task_id: str
    task_type: str

    @property
    def should_persist_history(self) -> bool:
        return self.persist_user_history or self.persist_ai_history


def _configurable_value(config: Optional[dict], key: str, default: Any) -> Any:
    if not config:
        return default
    configurable = config.get("configurable", {})
    if not isinstance(configurable, dict):
        return default
    return configurable.get(key, default)


def _configurable_list(config: Optional[dict], key: str) -> list[dict[str, Any]]:
    value = _configurable_value(config, key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _build_invocation_config(config: Optional[dict]) -> BuilderInvocationConfig:
    persist_history = bool(_configurable_value(config, "persist_history", True))
    return BuilderInvocationConfig(
        session_id=_configurable_value(config, "session_id", "default"),
        persist_history=persist_history,
        panel_id=str(_configurable_value(config, "panel_id", "") or ""),
        model_id=str(_configurable_value(config, "model_id", "") or ""),
        answer_group_id=str(_configurable_value(config, "answer_group_id", "") or ""),
        exclude_ai_answer_group_id=str(
            _configurable_value(config, "exclude_ai_answer_group_id", "") or ""
        ),
        persist_user_history=bool(
            _configurable_value(config, "persist_user_history", persist_history)
        ),
        persist_ai_history=bool(
            _configurable_value(config, "persist_ai_history", persist_history)
        ),
        replace_ai_history=bool(_configurable_value(config, "replace_ai_history", False)),
        raw_user_message=str(_configurable_value(config, "raw_user_message", "") or ""),
        raw_images=_configurable_list(config, "raw_images"),
        raw_files=_configurable_list(config, "raw_files"),
        task_id=str(_configurable_value(config, "task_id", "") or ""),
        task_type=str(_configurable_value(config, "task_type", "") or ""),
    )


def _attach_configured_task_meta(
    result: dict[str, Any],
    config: Optional[dict],
) -> dict[str, Any]:
    task_id = str(_configurable_value(config, "task_id", "") or "")
    task_type = str(_configurable_value(config, "task_type", "") or "")
    if task_id:
        result["task_id"] = task_id
    if task_type:
        result["task_type"] = task_type
    return result


def _build_workflow_snapshot(
    workflow_events: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    node_labels = {
        "classify_intent": "意图分类",
        "execute_tool": "工具执行",
        "generate_answer": "答案生成",
    }
    ordered_node_ids = [
        "classify_intent",
        "execute_tool",
        "generate_answer",
    ]
    snapshots: dict[str, dict[str, Any]] = {
        node_id: {
            "id": node_id,
            "name": node_id,
            "displayName": node_labels.get(node_id, node_id),
            "status": "pending",
        }
        for node_id in ordered_node_ids
    }

    for event in workflow_events or []:
        if not isinstance(event, dict) or event.get("type") != "workflow_state":
            continue
        node_name = str(event.get("node_name") or "").strip()
        if not node_name:
            continue

        node = snapshots.get(node_name)
        if node is None:
            node = {
                "id": node_name,
                "name": node_name,
                "displayName": node_labels.get(node_name, node_name),
                "status": "pending",
            }
            snapshots[node_name] = node
            ordered_node_ids.append(node_name)

        status = str(event.get("status") or node.get("status") or "pending")
        timestamp_raw = event.get("timestamp")
        try:
            timestamp = int(timestamp_raw) if timestamp_raw is not None else 0
        except (TypeError, ValueError):
            timestamp = 0

        if status == "running" and timestamp and not node.get("startTime"):
            node["startTime"] = timestamp
        if status in {"completed", "failed"} and timestamp:
            node["endTime"] = timestamp

        duration_raw = event.get("duration_ms")
        if duration_raw is not None:
            try:
                node["duration"] = int(duration_raw)
            except (TypeError, ValueError):
                pass
        elif node.get("startTime") and node.get("endTime"):
            node["duration"] = int(node["endTime"]) - int(node["startTime"])

        tool_name = str(event.get("tool_name") or "").strip()
        if tool_name:
            node["toolName"] = tool_name

        tool_params = event.get("tool_params")
        if isinstance(tool_params, dict) and tool_params:
            node["toolParams"] = tool_params

        tool_result = str(event.get("tool_result_summary") or "").strip()
        if tool_result:
            node["toolResult"] = tool_result

        retrieval_meta = event.get("retrieval_meta")
        if isinstance(retrieval_meta, dict) and retrieval_meta:
            node["retrievalMeta"] = retrieval_meta

        error = str(event.get("error") or "").strip()
        if error:
            node["error"] = error

        node["status"] = status

    return [snapshots[node_id] for node_id in ordered_node_ids]
