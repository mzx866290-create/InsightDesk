# LangGraph 模式快速开始

## 5 分钟上手指南

### 1. 安装依赖（1 分钟）

```bash
pip install langgraph>=0.2.0
```

或者重新安装所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 安装小模型（2 分钟）

选择一个小模型安装：

```bash
# 选项 1: Qwen3.5 4B（推荐，速度快）
ollama pull qwen3.5:4b

# 选项 2: Phi4 Mini（微软出品）
ollama pull phi4-mini

# 选项 3: Qwen2.5 7B（更强大，但需要更多资源）
ollama pull qwen2.5:7b
```

验证安装：

```bash
ollama list
```

### 3. 启动应用（1 分钟）

```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev -- --host 0.0.0.0 --port 3000
```

浏览器打开 `http://localhost:3000`

### 4. 配置 Agent 模式（1 分钟）

在侧边栏：

1. **模型类型**: 选择 `local`
2. **Model ID**: 选择你安装的模型（如 `qwen3.5:4b`）
3. **Agent 模式**: 选择 `auto` 或 `langgraph`
4. 点击 **🔄 应用配置**

等待初始化完成（约 5-10 秒）

### 5. 开始对话！

尝试以下问题：

```
你好
```
→ 测试基本对话

```
知识库里有多少文档?
```
→ 测试工具调用（知识库统计）

```
今天的新闻有什么?
```
→ 测试联网搜索

## 工作原理

```
你的问题 
    ↓
LLM 选择工具（输出 0-5）
    ↓
执行工具（如果需要）
    ↓
LLM 生成最终回答
    ↓
显示结果
```

**只需 2 次 LLM 调用，速度快！**

## 对比：为什么不用 Function Calling？

| 特性 | Function Calling | LangGraph |
|-----|-----------------|-----------|
| 小模型支持 | ❌ 不支持 | ✅ 支持 |
| 速度 | 快（如果支持） | 快 |
| 稳定性 | 高（如果支持） | 高 |
| qwen3.5:4b | ❌ 不可用 | ✅ 可用 |
| phi4-mini | ❌ 不可用 | ✅ 可用 |

## 常见问题

### Q: 提示 "模型未安装"？

A: 运行 `ollama pull <模型名>`，例如：
```bash
ollama pull qwen3.5:4b
```

### Q: 初始化很慢？

A: 第一次启动需要加载 embedding 模型（约 1GB），后续会快很多。

### Q: 如何查看详细日志？

A: 查看运行 `python -m uvicorn api_server:app --host 0.0.0.0 --port 8000` 的终端窗口，会显示：
- `[LangGraph] 工具选择: 1`
- `[LangGraph] 执行工具: query_knowledge`
- `[LangGraph] 生成回答: ...`

### Q: 可以同时使用多个模型吗？

A: 可以！在侧边栏切换模型和 Agent 模式，点击"应用配置"即可。

### Q: 速度还是慢怎么办？

A: 
1. 使用更小的模型（qwen3.5:2b）
2. 降低 Temperature（0.1-0.3）
3. 确保 Ollama 服务运行正常

## 下一步

- 📖 阅读完整文档：[LANGGRAPH_GUIDE.md](LANGGRAPH_GUIDE.md)
- 🧪 运行测试：`python scripts/manual_checks/langgraph_agent_smoke.py`
- 📁 上传文档，构建你的知识库
- 🎯 探索更多功能

## 需要帮助？

- 查看 [README.md](README.md) 了解完整功能
- 查看 [LANGGRAPH_GUIDE.md](LANGGRAPH_GUIDE.md) 了解技术细节
- 提交 Issue 报告问题

---

**享受快速、稳定的小模型 Agent 体验！** 🚀
> Update (2026-04-12)
>
> - The old `streamlit run app.py` flow is deprecated. The current app uses `FastAPI + React`.
> - Start the backend with `python -m uvicorn api_server:app --host 0.0.0.0 --port 8000`.
> - Start the frontend with `cd frontend && npm run dev -- --host 0.0.0.0 --port 3000`.
> - Manual smoke scripts were moved from the repo root to `scripts/manual_checks/`.
> - Replace old commands such as `python test_langgraph_agent.py` with
>   `python scripts/manual_checks/langgraph_agent_smoke.py`.
