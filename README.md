# InsightDesk

InsightDesk 是一个面向企业知识问答、资料分析与结果交付的 AI 工作台。  
它把聊天、知识库检索、附件分析、联网研究、会话记忆、异步任务、报告生成和 PPT 交付整合在同一个项目里。

## 项目定位

这个项目不是单纯的“聊天页面”或“RAG Demo”，而是一个更偏工作流闭环的 AI 应用底座，重点解决下面几类问题：

- 让企业内部资料变成可检索、可引用、可追溯的知识资产
- 让用户围绕同一个会话持续完成提问、分析、沉淀和交付
- 让会话结果可以继续沉淀为报告、Deck 和 `PPTX`
- 同时支持本地模型和云模型，适配不同成本与部署约束

## 核心能力

- 多工作区、多会话、多面板对话，支持答案对比、推荐答案提升、`continue / retry / fork`
- 知识库导入与检索，支持 `PDF / DOC / DOCX / TXT / Markdown / CSV / Excel`
- 检索调试与增强，支持 `semantic / keyword / hybrid` 三种模式
- 附件上传、附件追问、附件转知识库任务
- 会话记忆管理，支持手动固定与阶段性总结
- 异步任务中心，覆盖导入、分析、报告生成等任务场景
- 报告、Deck 与 `PPTX` 导出能力
- `function_calling`、`langgraph`、`auto` 三种 Agent 运行模式
- 工作流可视化、检索可观测性、安全状态与审计可见性

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、Zustand |
| 后端 | FastAPI、Uvicorn |
| Agent | LangChain、LangGraph |
| 模型接入 | Ollama、OpenAI-Compatible API、OpenRouter |
| 检索 | FAISS、sentence-transformers、CrossEncoder |
| 数据存储 | SQLite |
| 文档处理 | pypdf、docx2txt、mammoth、unstructured、pandas |
| 交付导出 | python-pptx |
| 部署 | Windows 脚本、Docker、docker compose |

## 目录结构

```text
.
├─ frontend/          React 前端
├─ backend/           FastAPI 接口、Agent 编排、业务服务
├─ search_runtime/    联网搜索与研究流程
├─ mcp_servers/       MCP 扩展服务
├─ tests/             后端测试与接口回归
├─ docs/              详细文档
├─ Dockerfile
├─ docker-compose.yml
├─ QUICKSTART.md
└─ README.md
```

## 快速开始

### 方式一：Windows 本地快速启动

1. 复制配置文件

```bash
copy .env.example .env
```

2. 配置至少一种模型接入方式

- 本地模型：配置 `OLLAMA_BASE_URL`，并准备好 Ollama 模型
- 云模型：配置 `OPENAI_API_KEY` 或 OpenRouter 对应配置

3. 运行启动脚本

```bash
start.bat
```

4. 打开前端

```text
http://localhost:5173
```

### 方式二：手动启动

1. 安装 Python 依赖

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

3. 复制配置文件

```bash
copy .env.example .env
```

4. 启动后端

```bash
python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
```

5. 启动前端

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

### 方式三：Docker

```bash
copy .env.example .env
docker compose up --build -d api
```

说明：

- 默认推荐的联网搜索路径是不使用 Docker，直接配置 `TAVILY_API_KEY`
- `docker compose` 默认只启动 `api` 和 `ollama`
- 启用 ARQ 队列时，将 `TASK_BACKEND=arq` 写入 `.env`，再运行 `docker compose --profile tasks up --build -d api redis worker`
- 启用 Qdrant 时，将 `VECTOR_STORE_PROVIDER=qdrant` 写入 `.env`，再运行 `docker compose --profile storage up --build -d api qdrant`
- 本地 `SearXNG` 改为可选能力，仅在显式启用 `search` profile 时启动
- 例如：`docker compose --profile search up -d searxng`
- 如果同时配置了可用的 `TAVILY_API_KEY`，运行时会优先使用 `tavily`
- 更完整的部署与运维命令见 [docs/DEPLOYMENT_OPERATIONS.md](./docs/DEPLOYMENT_OPERATIONS.md)

## 配置说明

常用环境变量可在 [`.env.example`](./.env.example) 中查看，重点包括：

- 模型配置：`OLLAMA_BASE_URL`、`OPENAI_API_KEY`、OpenRouter 相关项
- 联网搜索：`TAVILY_API_KEY`（推荐，非 Docker 默认方案）、`SEARXNG_URL`（可选，仅在手动启动本地 SearXNG 时使用）
- 远程访问保护：`APP_AUTH_TOKENS_JSON`、`ADMIN_API_TOKEN` 等
- 分享与安全：`SHARE_LINK_SECRET`、审计与安全状态相关配置

## 文档入口

- [QUICKSTART.md](./QUICKSTART.md)
  最短启动路径
- [docs/README.md](./docs/README.md)
  文档导航
- [docs/DELIVERY_STATUS.md](./docs/DELIVERY_STATUS.md)
  当前代码交付状态、已验证命令与剩余外部审批项
- [docs/USER_MANUAL.md](./docs/USER_MANUAL.md)
  项目功能说明书、使用方法与适用场景
- [docs/GETTING_STARTED.md](./docs/GETTING_STARTED.md)
  安装、模型模式与首次运行说明
- [docs/AGENT_AND_WORKFLOW.md](./docs/AGENT_AND_WORKFLOW.md)
  Agent 模式、LangGraph 与工作流可视化
- [docs/RESEARCH_LOGIC_V2.md](./docs/RESEARCH_LOGIC_V2.md)
  联网研究与搜索链路设计
- [docs/PRODUCT_ROADMAP.md](./docs/PRODUCT_ROADMAP.md)
  产品路线图与后续演进方向
- [docs/DECK_DELIVERY_PLAN.md](./docs/DECK_DELIVERY_PLAN.md)
  报告与 PPT 交付能力规划
- [docs/BACKEND_ARCHITECTURE.md](./docs/BACKEND_ARCHITECTURE.md)
  后端分层、入口职责与 `api_*` 兼容层边界
- [docs/STORAGE_RUNTIME.md](./docs/STORAGE_RUNTIME.md)
  SQLite ???????????? PostgreSQL ????
- [docs/DEPLOYMENT_OPERATIONS.md](./docs/DEPLOYMENT_OPERATIONS.md)
  Docker Compose、API、worker、Redis 与 Qdrant 部署运维说明
- [docs/IDENTITY_AND_ORGS.md](./docs/IDENTITY_AND_ORGS.md)
  ????????????
- [docs/RESOURCE_ACCESS.md](./docs/RESOURCE_ACCESS.md)
  ????????API ???????
- [docs/VALIDATION.md](./docs/VALIDATION.md)
  冒烟、回归与发布前检查

## 当前边界

当前项目已经具备较完整的产品骨架，但更适合作为团队内部可用的单机或轻量部署系统，而不是开箱即用的企业级多租户 SaaS。

当前边界主要包括：

- 默认仍以 `SQLite + 本地文件 + 本地 FAISS` 为主
- 已具备 token 鉴权、RBAC lite 与安全审计基础能力，但还不是完整用户体系
- 默认部署仍以单 API 进程为主；ARQ worker、Redis 与 Qdrant 已可通过 Compose profile 启用
- 更完整的组织级权限、监控告警、分布式任务与外部系统集成仍在持续演进

## 建议阅读顺序

1. [README.md](./README.md)
2. [QUICKSTART.md](./QUICKSTART.md)
3. [docs/GETTING_STARTED.md](./docs/GETTING_STARTED.md)
4. [docs/AGENT_AND_WORKFLOW.md](./docs/AGENT_AND_WORKFLOW.md)
5. [docs/PRODUCT_ROADMAP.md](./docs/PRODUCT_ROADMAP.md)

## 总结

InsightDesk 的重点不是“再做一个聊天机器人”，而是把企业知识问答、附件分析、会话沉淀、任务执行与交付输出串成一个更完整的工作闭环。  
如果你需要一个可本地部署、可继续工程化演进的 AI 工作台，这个项目已经具备不错的基础。

