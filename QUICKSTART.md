# 🚀 快速开始指南

## 5 分钟快速体验

### 方案 A: OpenRouter 云端模式 (推荐新手)

**优点**: 无需本地 GPU，配置简单，模型选择丰富

```bash
# 1. 运行安装脚本
setup.bat

# 2. 编辑 .env 文件 (会自动打开)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxx  # 从 https://openrouter.ai/settings/keys 获取
TAVILY_API_KEY=tvly-xxxxx          # (可选) 从 https://tavily.com/ 获取

# 3. 启动应用
start.bat
```

### 方案 B: Ollama 本地模式 (推荐企业内网)

**优点**: 数据不出网，完全私有，无 API 费用

```bash
# 1. 安装 Ollama
# 访问 https://ollama.com/download/windows 下载安装

# 2. 拉取模型
ollama pull qwen2.5:7b

# 3. 运行安装脚本
setup.bat

# 4. 编辑 .env 文件
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
TAVILY_API_KEY=tvly-xxxxx  # (可选) 联网搜索功能

# 5. 启动应用
start.bat
```

## 第一次使用

### 1. 上传测试文档

系统已包含测试文档 `test_doc.md`，可以直接在界面上传：

1. 点击侧边栏 "📁 文档管理"
2. 上传 `test_doc.md`
3. 点击 "📥 导入知识库"
4. 等待处理完成

### 2. 测试问答

尝试以下问题：

**内部知识库问题**:
- "公司主要产品有哪些？"
- "技术栈是什么？"
- "如何联系公司？"

**联网搜索问题** (需配置 TAVILY_API_KEY):
- "今天的新闻有什么？"
- "Python 最新版本是什么？"
- "LangChain 是什么？"

## 常见问题速查

### ❌ "Agent 初始化失败"

**Ollama 模式**:
```bash
# 检查 Ollama 是否运行
ollama list

# 如果未运行，启动服务
ollama serve
```

**OpenRouter 模式**:
- 检查 `.env` 中的 `OPENROUTER_API_KEY` 是否正确
- 确认 API Key 有余额

### ❌ "知识库未初始化"

- 需要先上传文档并导入
- 或者上传测试文档 `test_doc.md`

### ❌ "联网搜索失败"

- 检查 `.env` 中的 `TAVILY_API_KEY` 是否配置
- 确认网络连接正常

### ⚠️ 首次运行很慢

第一次运行时会下载 Embedding 模型 (约 1.3GB)，请耐心等待。

模型会缓存到:
- Windows: `C:\Users\你的用户名\.cache\huggingface`
- Linux: `~/.cache/huggingface`

## 下一步

- 📖 阅读完整文档: [README.md](README.md)
- 🔧 自定义配置: 编辑 `.env` 和 `doc_pipeline.py`
- 🚀 部署到生产: 参考 README 中的生产部署章节
- 🤝 贡献代码: 提交 Issue 或 PR

## 推荐模型

### OpenRouter 免费模型
- `google/gemini-2.0-flash-exp:free` - 快速，免费
- `meta-llama/llama-3.1-8b-instruct:free` - 开源，免费

### OpenRouter 付费模型 (效果更好)
- `qwen/qwen-2.5-72b-instruct` - 中文能力强
- `anthropic/claude-sonnet-4.5` - 综合能力强
- `deepseek/deepseek-chat` - 性价比高

### Ollama 本地模型
- `qwen2.5:7b` - 推荐，中文能力强
- `llama3.1:8b` - 英文能力强
- `deepseek-r1:7b` - 推理能力强

## 获取帮助

遇到问题？
1. 查看终端错误日志
2. 检查 `.env` 配置
3. 阅读 [README.md](README.md) 常见问题章节
4. 提交 Issue

---

祝使用愉快！🎉
# Windows 同事启动方式

推荐给不懂代码的同事直接双击项目根目录里的 `一键启动.bat`。

这个启动器会自动完成这些事情：
- 检查 `Python`、`Node.js`、`npm`
- 自动创建 `venv312` 并安装后端依赖
- 自动安装 `frontend` 前端依赖
- 如果缺少 `.env`，会自动从 `.env.example` 复制
- 按 `.env` 中的 `LLM_PROVIDER` 自动检查 `Ollama` 或 `OpenRouter`
- 启动新版 `React + FastAPI`
- 自动打开浏览器到 `http://localhost:3000`
- 在窗口里打印局域网访问地址，方便同网段同事访问

同事只需要记住：
1. 双击 `一键启动.bat`
2. 看到浏览器打开后，使用 `http://localhost:3000`
3. 如果要给局域网其他同事访问，把窗口里显示的 `http://<你的电脑IP>:3000` 发给对方

常见说明：
- 如果 `.env` 里使用 `openrouter`，需要先把 `OPENROUTER_API_KEY` 改成真实值
- 如果 `.env` 里使用 `ollama`，启动器会尝试自动启动 Ollama，并在模型缺失时自动拉取模型
- 如果局域网地址打不开，优先检查两台电脑是否在同一网络，以及 Windows 防火墙是否放行 `3000` 和 `8000` 端口
