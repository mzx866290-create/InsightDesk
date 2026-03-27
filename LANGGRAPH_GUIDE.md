# LangGraph 轻量 Agent 使用指南

## 概述

本项目现在支持两种 Agent 模式：

1. **Function Calling 模式**：使用模型原生的工具调用能力（需要模型支持）
2. **LangGraph 轻量模式**：专为小模型设计的轻量级 Agent，最多 2 次 LLM 调用

## 为什么需要 LangGraph 模式？

小模型（如 qwen3.5:2b/4b、phi4-mini）**不支持** Function Calling 协议，使用 `create_tool_calling_agent` 会失败。

传统的 ReAct 框架虽然兼容所有模型，但对小模型来说：
- 需要多轮 LLM 调用（5-10 次）
- 格式要求严格（Thought/Action/Action Input）
- 小模型容易输出不规范，导致解析失败、重试循环
- **结果：速度慢、容易卡死**

LangGraph 轻量模式的优势：
- ✅ 最多 2 次 LLM 调用（选工具 + 生成回答）
- ✅ 工具选择只需输出一个数字（0-5），对小模型极友好
- ✅ 无循环、无复杂格式解析，不会卡死
- ✅ 仍使用 LangChain/LangGraph 生态组件

## 架构

```
用户提问
    ↓
第1步: LLM 选工具 (输出 0-5 的数字)
    ↓
需要工具? → 执行工具 → 第2步: LLM 生成回答
    ↓
不需要工具? → 直接生成回答
    ↓
最终回答
```

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

新增依赖：`langgraph>=0.2.0`

### 2. 在 Streamlit UI 中使用

启动应用：

```bash
streamlit run app.py
```

在侧边栏的 **Agent 模式** 下拉框中选择：

- **auto**（推荐）：本地模型自动使用 LangGraph，云端模型使用 Function Calling
- **langgraph**：强制使用 LangGraph 轻量模式
- **function_calling**：强制使用 Function Calling（需要模型支持）

### 3. 在代码中使用

```python
from agent_core import build_agent

# 方式 1: auto 模式（推荐）
agent = await build_agent(
    provider="local",
    model_name="qwen3.5:4b",
    agent_mode="auto",  # 本地模型自动用 LangGraph
)

# 方式 2: 显式指定 langgraph 模式
agent = await build_agent(
    provider="local",
    model_name="phi4-mini",
    agent_mode="langgraph",  # 强制使用 LangGraph
)

# 调用 agent
result = await agent.ainvoke(
    {"input": "知识库里有多少文档?"},
    config={"configurable": {"session_id": "my-session"}}
)

print(result["output"])
```

### 4. 测试

运行测试脚本：

```bash
python test_langgraph_agent.py
```

测试脚本会：
- 初始化 LangGraph agent
- 测试多个查询（打招呼、知识库查询、联网搜索）
- 显示每次查询的耗时
- 验证对话记忆功能

## 支持的模型

### LangGraph 模式（推荐用于以下模型）

- ✅ qwen3.5:2b / qwen3.5:4b
- ✅ phi4-mini
- ✅ qwen2.5:7b（也可用，但更推荐 Function Calling）
- ✅ 任何文本生成模型

### Function Calling 模式（需要模型支持）

- ✅ qwen2.5:7b 及以上
- ✅ GPT-3.5/4, Claude 等云端大模型
- ✅ 支持 OpenAI Function Calling 协议的模型

## 配置建议

| 模型类型 | 推荐 Agent 模式 | 原因 |
|---------|----------------|------|
| qwen3.5:2b/4b | langgraph | 小模型不支持 Function Calling |
| phi4-mini | langgraph | 小模型不支持 Function Calling |
| qwen2.5:7b | auto / function_calling | 支持 Function Calling，但 LangGraph 也可用 |
| GPT-4, Claude | auto / function_calling | 云端大模型，Function Calling 更强大 |

## 工具列表

LangGraph agent 支持以下工具：

1. **query_knowledge** - 查询企业知识库
2. **web_search** - 联网搜索
3. **quick_answer** - 快速联网问答
4. **get_knowledge_stats** - 知识库统计
5. **reload_knowledge_base** - 重载知识库

## 性能对比

| Agent 模式 | LLM 调用次数 | 小模型稳定性 | 速度 |
|-----------|-------------|-------------|------|
| Function Calling | 1-2 次 | ❌ 不支持 | 快 |
| ReAct | 5-10 次 | ❌ 容易卡死 | 慢 |
| LangGraph 轻量 | 2 次 | ✅ 稳定 | 快 |

## 常见问题

### Q: 为什么选择 LangGraph 而不是 ReAct？

A: ReAct 对小模型来说太复杂：
- 需要输出严格的 Thought/Action/Action Input 格式
- 小模型经常输出不规范，导致解析失败
- 需要多轮循环，速度慢

LangGraph 只需要输出一个数字（0-5），对小模型极友好。

### Q: LangGraph 模式支持对话记忆吗？

A: 支持！通过 `session_id` 管理多轮对话记忆，与 Function Calling 模式完全一致。

### Q: 可以混合使用两种模式吗？

A: 可以！使用 `agent_mode="auto"`，系统会根据 provider 自动选择：
- 本地模型 → LangGraph
- 云端模型 → Function Calling

### Q: 如何切换模式？

A: 在 Streamlit UI 的侧边栏选择 Agent 模式，或在代码中设置 `agent_mode` 参数。

## 技术细节

### LangGraph 工作流程

1. **classify_intent 节点**：LLM 根据用户问题选择工具编号（0-5）
2. **条件边**：判断是否需要使用工具
3. **execute_tool 节点**：执行选定的工具
4. **generate_answer 节点**：基于工具结果生成最终回答

### 对话记忆集成

LangGraph agent 通过自定义 wrapper 类集成对话记忆：
- 调用前：从 `InMemoryChatMessageHistory` 读取历史消息
- 调用中：通过 state 的 `chat_history` 字段传递给 LLM
- 调用后：更新历史记录

### 返回格式兼容

LangGraph agent 的返回格式与 `AgentExecutor` 完全一致：

```python
{"output": "最终回答"}
```

确保与现有代码无缝集成。

## 下一步

1. 安装你想测试的小模型：
   ```bash
   ollama pull qwen3.5:4b
   ollama pull phi4-mini
   ```

2. 运行测试脚本验证功能

3. 在 Streamlit UI 中选择 LangGraph 模式开始使用

4. 享受快速、稳定的小模型 Agent 体验！
