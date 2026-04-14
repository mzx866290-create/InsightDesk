# LangGraph 工作流可视化与人工干预实施指南

## 概述

本指南说明如何将 LangGraph 节点执行流程实时可视化到前端，让用户看到 AI 的"思考过程"，从而产生极强的掌控感和信任感。

---

## 架构设计

### 后端流程
```
LangGraph Agent 执行
    ↓
WorkflowStateCallback 捕获节点事件
    ↓
推送 workflow_state 事件到前端 (SSE/WebSocket)
    ↓
前端接收并更新 workflowStore
    ↓
WorkflowVisualizer 实时渲染
```

### 前端流程
```
ChatPanel 初始化 → initWorkflow(panelId)
    ↓
streamSingleChat 开始流式传输
    ↓
onChunk 回调接收 workflow_state 事件
    ↓
parseWorkflowEvent 解析事件
    ↓
updateNodeStatus 更新 workflowStore
    ↓
WorkflowVisualizer 自动重新渲染
```

---

## 实施步骤

### 第一步：后端集成（agent_core.py）

在 `build_langgraph_agent` 函数中，为三个节点添加工作流状态回调：

```python
from agent_core_workflow_patch import WorkflowStateCallback

async def build_langgraph_agent(...):
    # ... 现有代码 ...
    
    # 创建工作流回调（暂时为空，后续通过 SSE 推送）
    workflow_callback = WorkflowStateCallback(on_state_change=lambda x: None)
    
    async def classify_intent(state: AgentState) -> AgentState:
        workflow_callback.on_node_start("classify_intent", state)
        try:
            # ... 原有意图分类逻辑 ...
            workflow_callback.on_node_end("classify_intent", state, success=True)
            return state
        except Exception as e:
            workflow_callback.on_node_end("classify_intent", state, success=False)
            raise
    
    async def execute_tool(state: AgentState) -> AgentState:
        workflow_callback.on_node_start("execute_tool", state)
        try:
            # ... 原有工具执行逻辑 ...
            workflow_callback.on_node_end("execute_tool", state, success=True)
            return state
        except Exception as e:
            workflow_callback.on_node_end("execute_tool", state, success=False)
            raise
    
    async def generate_answer(state: AgentState) -> AgentState:
        workflow_callback.on_node_start("generate_answer", state)
        try:
            # ... 原有答案生成逻辑 ...
            workflow_callback.on_node_end("generate_answer", state, success=True)
            return state
        except Exception as e:
            workflow_callback.on_node_end("generate_answer", state, success=False)
            raise
    
    # ... 构建 workflow 和返回 ...
```

### 第二步：前端集成（ChatPanel.tsx）

已完成的改动：
- ✅ 导入 `useWorkflowStore` 和 `WorkflowVisualizer`
- ✅ 在流式传输时显示工作流可视化面板
- ✅ 添加 Eye/EyeOff 按钮切换可视化显示

### 第三步：流式事件处理（streamControl.ts）

在 `streamSingleChat` 的 `onChunk` 回调中添加工作流事件处理：

```typescript
import { parseWorkflowEvent } from '../api/workflowClient'

// 在 streamSingleChat 的 onChunk 回调中
onChunk((chunk) => {
  // 处理工作流状态事件
  const workflowEvent = parseWorkflowEvent(chunk)
  if (workflowEvent) {
    const { updateNodeStatus } = useWorkflowStore.getState()
    updateNodeStatus(panelId, workflowEvent.node_name, workflowEvent.status, {
      toolName: workflowEvent.tool_name,
      toolParams: workflowEvent.tool_params,
      toolResult: workflowEvent.tool_result_summary,
      error: workflowEvent.error,
    })
    return
  }
  
  // ... 处理其他事件类型 ...
})
```

---

## 工作流事件格式

### 节点开始事件
```json
{
  "type": "workflow_state",
  "node_name": "classify_intent",
  "status": "running",
  "timestamp": 1712500000000
}
```

### 工具执行事件
```json
{
  "type": "workflow_state",
  "node_name": "execute_tool",
  "status": "running",
  "tool_name": "query_knowledge",
  "tool_params": {
    "question": "知识库里有什么?"
  },
  "timestamp": 1712500001000
}
```

### 节点完成事件
```json
{
  "type": "workflow_state",
  "node_name": "execute_tool",
  "status": "completed",
  "duration_ms": 2345,
  "tool_result_summary": "找到 5 份相关文档...",
  "timestamp": 1712500003345
}
```

### 节点失败事件
```json
{
  "type": "workflow_state",
  "node_name": "generate_answer",
  "status": "failed",
  "error": "LLM request timed out",
  "duration_ms": 60000,
  "timestamp": 1712500063000
}
```

---

## 前端组件说明

### WorkflowVisualizer 组件

显示三个节点的执行状态：

```
✓ 意图分类 (已完成)
⏳ 工具执行 (进行中)
   └─ 工具: query_knowledge
   └─ 参数: question="知识库里有什么?"
⭕ 答案生成 (等待中)
```

**特性**：
- 实时更新节点状态
- 显示工具名称和参数
- 显示执行耗时
- 错误提示

### workflowStore 状态管理

```typescript
interface WorkflowNode {
  id: string                    // 节点 ID
  name: string                  // 节点名称
  displayName: string           // 显示名称
  status: 'pending' | 'running' | 'completed' | 'failed'
  startTime?: number            // 开始时间戳
  endTime?: number              // 结束时间戳
  duration?: number             // 执行耗时（毫秒）
  toolName?: string             // 工具名称
  toolParams?: Record<string, any>  // 工具参数
  toolResult?: string           // 工具结果摘要
  error?: string                // 错误信息
}
```

---

## 人工干预（第二阶段）

### 高风险操作检测

对于以下操作，在执行前暂停并请求用户确认：

1. **知识库重载** (`reload_knowledge_base`)
   - 可能影响所有用户的知识库
   - 需要用户明确授权

2. **文件操作**（未来扩展）
   - 删除、覆盖文件
   - 修改系统配置

### 实施方式

在 `execute_tool` 节点前添加 `human_approval` 节点：

```python
async def human_approval(state: AgentState) -> AgentState:
    """检查是否需要人工审批"""
    tool_choice = state.get("tool_choice", "")
    
    # 高风险工具列表
    high_risk_tools = {"5"}  # reload_knowledge_base
    
    if tool_choice in high_risk_tools:
        # 发送审批请求到前端
        state["approval_required"] = True
        state["approval_message"] = f"即将执行高风险操作：{_get_tool_name(tool_choice)}"
        return state
    
    state["approval_required"] = False
    return state
```

前端弹出确认卡片：

```typescript
if (chunk.type === 'approval_required') {
  // 显示确认对话框
  const confirmed = await showApprovalDialog(chunk.message)
  if (!confirmed) {
    // 用户拒绝，停止执行
    controller.abort()
  }
}
```

---

## 测试清单

- [ ] 后端成功推送 workflow_state 事件
- [ ] 前端正确接收并解析事件
- [ ] WorkflowVisualizer 实时更新节点状态
- [ ] 节点耗时计算正确
- [ ] 工具名称和参数正确显示
- [ ] 错误信息正确显示
- [ ] Eye/EyeOff 按钮切换显示/隐藏
- [ ] 多个 Panel 的工作流独立显示
- [ ] 高风险操作正确触发审批流程

---

## 性能优化建议

1. **事件节流**：避免过于频繁的状态更新
2. **内存管理**：完成后清理工作流状态
3. **网络优化**：使用 SSE 而非 WebSocket 减少连接开销
4. **UI 优化**：使用 React.memo 避免不必要的重新渲染

---

## 下一步

1. 集成后端工作流状态推送
2. 测试前端可视化效果
3. 实施人工干预审批流程
4. 收集用户反馈并迭代优化
