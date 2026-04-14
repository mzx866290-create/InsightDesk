"""
LangGraph Agent 工作流状态推送补丁
将此代码集成到 agent_core.py 的 build_langgraph_agent 函数中
"""

import json
import asyncio
from typing import Any, Callable, Optional

class WorkflowStateCallback:
    """捕获 LangGraph 节点执行事件并推送到前端"""
    
    def __init__(self, on_state_change: Optional[Callable[[dict[str, Any]], None]] = None):
        self.on_state_change = on_state_change or (lambda x: None)
        self.node_start_times: dict[str, float] = {}
    
    def on_node_start(self, node_name: str, state: dict[str, Any]) -> None:
        """节点开始执行"""
        import time
        self.node_start_times[node_name] = time.time()
        
        payload = {
            "type": "node_state",
            "node_name": node_name,
            "status": "running",
            "timestamp": int(time.time() * 1000),
        }
        
        # 提取工具信息
        if node_name == "execute_tool":
            tool_choice = state.get("tool_choice", "")
            if tool_choice and tool_choice != "0":
                payload["tool_name"] = self._get_tool_name(tool_choice)
                payload["tool_params"] = {"tool_id": tool_choice}
        
        self.on_state_change(payload)
    
    def on_node_end(self, node_name: str, state: dict[str, Any], success: bool = True) -> None:
        """节点执行完成"""
        import time
        now = time.time()
        start_time = self.node_start_times.get(node_name, now)
        duration_ms = int((now - start_time) * 1000)
        
        payload = {
            "type": "node_state",
            "node_name": node_name,
            "status": "completed" if success else "failed",
            "duration_ms": duration_ms,
            "timestamp": int(now * 1000),
        }
        
        # 提取工具结果摘要
        if node_name == "execute_tool" and success:
            tool_result = state.get("tool_result", "")
            if tool_result:
                # 只取前 200 字符作为摘要
                summary = tool_result[:200].replace("\n", " ")
                payload["tool_result_summary"] = summary
        
        self.on_state_change(payload)
    
    def _get_tool_name(self, tool_choice: str) -> str:
        """根据工具编号返回工具名称"""
        tool_names = {
            "1": "query_knowledge",
            "2": "web_search",
            "3": "quick_answer",
            "4": "get_knowledge_stats",
            "5": "reload_knowledge_base",
            "6": "fetch_webpage",
        }
        return tool_names.get(tool_choice, f"tool_{tool_choice}")


# 集成到 build_langgraph_agent 中的修改示例
# 在 build_langgraph_agent 函数中添加以下代码：

"""
# 创建工作流状态回调
workflow_callback = WorkflowStateCallback(on_state_change=lambda payload: None)

# 修改 classify_intent 节点
async def classify_intent(state: AgentState) -> AgentState:
    workflow_callback.on_node_start("classify_intent", state)
    try:
        # ... 原有逻辑 ...
        workflow_callback.on_node_end("classify_intent", state, success=True)
        return state
    except Exception as e:
        workflow_callback.on_node_end("classify_intent", state, success=False)
        raise

# 修改 execute_tool 节点
async def execute_tool(state: AgentState) -> AgentState:
    workflow_callback.on_node_start("execute_tool", state)
    try:
        # ... 原有逻辑 ...
        workflow_callback.on_node_end("execute_tool", state, success=True)
        return state
    except Exception as e:
        workflow_callback.on_node_end("execute_tool", state, success=False)
        raise

# 修改 generate_answer 节点
async def generate_answer(state: AgentState) -> AgentState:
    workflow_callback.on_node_start("generate_answer", state)
    try:
        # ... 原有逻辑 ...
        workflow_callback.on_node_end("generate_answer", state, success=True)
        return state
    except Exception as e:
        workflow_callback.on_node_end("generate_answer", state, success=False)
        raise
"""
