# LangGraph 轻量 Agent 实施总结

## 实施日期
2026-03-24

## 问题背景

用户反馈本地小模型（qwen3.5、phi4-mini）不支持 Function Calling 框架，尝试使用 ReAct 框架但速度太慢容易卡死。

## 解决方案

实施了基于 LangGraph 的轻量级 Agent 模式，专为小模型优化：

### 核心优势
- ✅ 最多 2 次 LLM 调用（vs ReAct 的 5-10 次）
- ✅ 工具选择只需输出数字 0-5（vs ReAct 的复杂格式）
- ✅ 无循环、无复杂解析，不会卡死
- ✅ 完全兼容现有 LangChain 生态

### 架构设计

```
用户输入 → classify_intent (选工具) → 条件判断
                                         ↓
                              需要工具? → execute_tool
                                         ↓
                              不需要? → generate_answer → 输出
```

## 实施内容

### 1. 依赖更新
- **文件**: `requirements.txt`
- **变更**: 添加 `langgraph>=0.2.0`

### 2. 核心代码 - agent_core.py

#### 2.1 新增导入
```python
from typing import TypedDict, Annotated, Literal
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
```

#### 2.2 工具函数抽取
- 创建 `create_tools(pipeline)` 函数
- 将原有的 5 个 `@tool` 函数抽取为可复用组件
- 工具列表：query_knowledge, reload_knowledge_base, get_knowledge_stats, web_search, quick_answer

#### 2.3 LangGraph Agent 构建
- 定义 `AgentState` TypedDict（input, chat_history, tool_choice, tool_result, output）
- 实现 3 个节点：
  - `classify_intent`: LLM 输出 0-5 选择工具
  - `execute_tool`: 根据编号执行对应工具
  - `generate_answer`: 基于工具结果生成最终回答
- 实现条件边 `should_use_tool`: 判断是否需要工具
- 编译为 StateGraph

#### 2.4 对话记忆集成
- 创建 `LangGraphAgentWrapper` 类
- 在 `ainvoke` 中自动管理 `InMemoryChatMessageHistory`
- 调用前读取历史，调用后更新历史
- 返回格式兼容 `{"output": "答案"}`

#### 2.5 build_agent 重构
- 新增 `agent_mode` 参数：`"auto"`, `"function_calling"`, `"langgraph"`
- `"auto"` 模式：本地用 LangGraph，云端用 Function Calling
- 保持向后兼容，默认行为不变

### 3. 历史 UI 更新 - app.py（已迁移）

#### 3.1 配置状态
- `agent_config` 新增 `"agent_mode": "auto"` 字段

#### 3.2 侧边栏控件
- 新增 Agent 模式下拉框（auto / langgraph / function_calling）
- 添加帮助文本说明各模式适用场景

#### 3.3 Agent 构建
- `build_agent_sync` 传递 `agent_mode` 参数
- 初始化和配置更新时都支持 agent_mode
- 状态栏显示当前 Agent 模式

### 4. 测试脚本
- **文件**: `scripts/manual_checks/langgraph_agent_smoke.py`
- **功能**: 
  - 测试 LangGraph agent 初始化
  - 测试多种查询类型（闲聊、知识库、联网搜索）
  - 测量每次调用耗时
  - 验证对话记忆功能

### 5. 文档
- **LANGGRAPH_GUIDE.md**: 详细使用指南
  - 架构说明
  - 使用方法
  - 模型兼容性
  - 性能对比
  - 常见问题
- **README.md**: 更新主文档
  - 核心特性增加小模型优化说明
  - 切换模型部分增加 Agent 模式说明
  - 技术栈更新
  - 常见问题新增 LangGraph 相关内容

## 代码变更统计

| 文件 | 变更类型 | 行数 |
|------|---------|------|
| requirements.txt | 新增 | +1 |
| agent_core.py | 重构+新增 | +300 |
| app.py | 历史文件（已移除） | +15 |
| scripts/manual_checks/langgraph_agent_smoke.py | 新位置 | +100 |
| LANGGRAPH_GUIDE.md | 新增 | +200 |
| README.md | 修改 | +30 |
| IMPLEMENTATION_SUMMARY.md | 新增 | 本文件 |

## 兼容性保证

### 向后兼容
- ✅ 默认 `agent_mode="auto"` 保持原有行为
- ✅ Function Calling 模式完全保留
- ✅ 返回格式统一为 `{"output": "答案"}`
- ✅ 对话记忆机制一致

### 新增功能
- ✅ 支持小模型（qwen3.5, phi4-mini）
- ✅ 可手动选择 Agent 模式
- ✅ 更快的响应速度（对小模型）

## 使用指南

### 快速开始

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 启动应用：
```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev -- --host 0.0.0.0 --port 3000
```

3. 在侧边栏选择 Agent 模式：
   - **auto**（推荐）：自动选择最优模式
   - **langgraph**：强制使用轻量模式
   - **function_calling**：强制使用原生工具调用

### 测试验证

```bash
python scripts/manual_checks/langgraph_agent_smoke.py
```

### 代码调用

```python
from agent_core import build_agent

# 小模型推荐配置
agent = await build_agent(
    provider="local",
    model_name="qwen3.5:4b",
    agent_mode="auto",  # 或 "langgraph"
)

result = await agent.ainvoke(
    {"input": "你好"},
    config={"configurable": {"session_id": "test"}}
)
print(result["output"])
```

## 性能对比

| Agent 模式 | 小模型支持 | LLM 调用次数 | 稳定性 | 速度 |
|-----------|-----------|-------------|--------|------|
| Function Calling | ❌ 不支持 | 1-2 | N/A | N/A |
| ReAct | ✅ 支持 | 5-10 | ❌ 易卡死 | 慢 |
| LangGraph | ✅ 支持 | 2 | ✅ 稳定 | 快 |

## 已知限制

1. **工具参数提取**: 当前使用用户原始问题作为工具输入，未做参数提取。对于复杂参数场景可能需要优化。

2. **工具选择准确性**: 依赖 LLM 理解能力，小模型可能偶尔选错工具。可通过优化 prompt 改进。

3. **多工具链式调用**: 当前只支持单次工具调用，不支持"先查知识库再联网搜索"这类链式场景。

## 未来优化方向

1. **参数提取**: 增加 LLM 提取工具参数的步骤
2. **多工具支持**: 支持一次查询调用多个工具
3. **Prompt 优化**: 针对不同模型优化分类 prompt
4. **缓存机制**: 对常见查询缓存工具选择结果
5. **监控指标**: 添加工具选择准确率、响应时间等监控

## 验收标准

- [x] 支持 qwen3.5、phi4-mini 等小模型
- [x] 响应速度快，不卡死
- [x] 保持对话记忆功能
- [x] 向后兼容现有代码
- [x] UI 支持模式切换
- [x] 文档完整清晰
- [x] 测试脚本可用

## 总结

成功实施了 LangGraph 轻量 Agent 方案，解决了小模型不支持 Function Calling 的问题。通过简化工具选择流程（数字选择）和减少 LLM 调用次数（最多 2 次），显著提升了小模型的可用性和响应速度。

该方案完全兼容现有系统，用户可以根据模型能力灵活选择 Agent 模式，实现了"大模型用 Function Calling，小模型用 LangGraph"的最优配置。
> Update (2026-04-12)
>
> This summary contains historical references from the earlier Streamlit phase.
> For the current repo layout:
>
> - `app.py` has been removed.
> - The active stack is `FastAPI + React`.
> - Root-level manual test scripts were reorganized into `scripts/manual_checks/`.
