# InsightDesk 优化实施计划

## 目标

将 InsightDesk 从"具备完整产品骨架的 AI 工作台原型"演进为"可支撑企业级知识分析与交付的多 Agent 协作平台"。

演进分四个阶段：

1. 架构治理与核心拆分
2. Agent 能力升级与新 Agent 落地
3. 研究管线与交付管线强化
4. 生产化与生态扩展

每个阶段内部按 P0 / P1 / P2 标注优先级。阶段之间有依赖关系，但阶段内部的 P1 / P2 任务允许并行。

---

## 当前状态快照

### 已有能力

- 三模式 Agent 编排（function_calling / langgraph / auto）
- 6 个内置工具（知识库查询、联网搜索、快速问答、网页抓取、知识库统计、知识库重载）
- semantic / keyword / hybrid + rerank 检索
- 4 个搜索 Provider（Tavily / DuckDuckGo / Bing / SearXNG）
- 多工作区、多会话、多面板对话
- 会话记忆（手动固定 + 阶段性总结）
- 异步任务中心
- 报告 / Deck / PPTX 交付管线
- Token 鉴权、RBAC lite、安全审计
- 工作流可视化
- 54 个后端测试文件

### 当前实际进度（2026-04-25）

以下内容已落地，但尚未完全反映到原始阶段规划中：

1. 身份与组织基础能力已完成
   - 已增加 `organizations`、`users`、`memberships` 持久化存储
   - 已提供 `/api/identity`、`/api/identity/orgs`、`/api/identity/users`、`/api/identity/memberships`

2. 资源级授权与继承已完成
   - 已增加 `resource_grants` 存储与 `/api/access/resource-grants`
   - 已支持 `workspace`、`session`、`deck`、`artifact`、`task` 等资源的 ACL
   - 已实现 `session -> task`、`session -> deck`、`session -> artifact` 授权继承
   - 已加入最后一个 `owner` 不可降级/删除保护

3. 资源可见性过滤已在关键列表接口生效
   - `workspace`、`session` 列表已按资源 ACL 过滤
   - `deck`、`artifact` 已补充全局列表接口，供管理端资源选择器复用

4. 前端权限管理入口已完成第一轮产品化
   - 设置页已新增“身份与组织管理”面板
   - 设置页已新增“资源访问控制”面板
   - 已支持资源选择器与主体选择器，降低手工输入成本

5. 阶段一原始 P0 已完成核心拆分验收线
   - `backend/agent_core.py` 已降为 59 行兼容 re-export
   - `backend/agent/runtime_support.py` 已降为 269 行兼容聚合层
   - `backend/agent/builder.py`、`backend/agent/langgraph.py` 与新增 wrapper/helper 拆分产物均已控制在 600 行以内
   - `backend/agent/tools.py`、`runtime_tools.py`、`builder.py`、`langgraph.py` 已从 `runtime_support` 通配导入改为显式依赖
   - 因此当前状态是“主入口兼容层已达标，focused modules 行数已过线，剩余工作转为全量回归与 timeout fallback 聚焦迁移”

### 核心瓶颈

| 瓶颈 | 影响范围 | 严重度 |
| --- | --- | --- |
| `runtime_support.py` 仍保留 timeout fallback 兼容实现 | 可维护性、职责边界 | 中 |
| SQLite + 本地 FAISS，无法水平扩展 | 并发、数据量 | 中高 |
| 单 Agent 编排，无多 Agent 协作 | 复杂任务能力 | 高 |
| Research V2 设计完整但代码未落地 | 研究质量 | 中 |
| 缺乏生产级可观测性 | 运维效率 | 中 |
| MCP 连接器未产品化 | 扩展能力 | 中 |

---

## 阶段一：架构治理与核心拆分

目标：在不改变外部行为的前提下，将代码结构调整到支撑多 Agent 架构的状态。

预计周期：3-4 周

### 1.1 拆分 agent_core.py（P0）

原始 `backend/agent_core.py` 承担了模型连接、工具注册、检索逻辑、Prompt 工程、附件处理、历史压缩等全部职责。

拆分方案：

```text
backend/agent_core.py (原始 4916 行，当前 59 行兼容层)
  ├── backend/agent/connection.py        模型连接与归一化
  ├── backend/agent/tools.py             工具注册、发现、启用
  ├── backend/agent/retrieval.py         检索模式选择、KB 文档检索
  ├── backend/agent/prompts.py           系统提示构建、业务格式指令
  ├── backend/agent/sources.py           来源提取、附件来源构建、来源合并
  ├── backend/agent/history.py           历史压缩、文件上下文折叠
  ├── backend/agent/dashboard.py         仪表盘生成编排
  ├── backend/agent/dashboard_payload.py 仪表盘 payload 归一化与渲染
  ├── backend/agent/dashboard_attachments.py 附件解析、表格解析与 fallback 仪表盘
  ├── backend/agent/llm.py              LLM 调用超时、结果压缩
  ├── backend/agent/builder.py           Agent wrapper 编排入口
  ├── backend/agent/builder_context.py   配置读取、任务元数据与 workflow 快照 helper
  ├── backend/agent/builder_history.py   会话历史加载与面板历史持久化
  ├── backend/agent/builder_streaming.py wrapper 统一 ainvoke 与 LangGraph 流式循环
  ├── backend/agent/builder_wrappers.py  LangGraph / plain chat / function calling wrapper 适配层
  ├── backend/agent/langgraph.py         LangGraph 节点编排入口
  ├── backend/agent/langgraph_helpers.py 查询改写、状态类型与 workflow 事件投递 helper
  ├── backend/agent/executor.py          Agent 执行入口（function_calling + langgraph）
  └── backend/agent/__init__.py          公共导出，保持外部导入兼容
```

执行步骤：

1. 创建 `backend/agent/` 包目录
2. 按模块逐个迁移函数和类，每次迁移后运行全量测试
3. 在 `backend/agent_core.py` 中保留兼容性 re-export
4. 更新 `backend/services/agent_core.py` 的代理指向
5. 确保 54 个测试文件全部通过

验收标准：

- `agent_core.py` 降到 200 行以内（仅保留 re-export）
- 每个新模块不超过 600 行
- 所有现有测试通过，无行为变更

当前实际状态说明：

- `backend/agent_core.py` 已降为 59 行兼容 re-export，并通过 `backend.agent` / `backend.services.agent_core` 保持旧导入与 monkeypatch 兼容
- 已新增 `backend/agent/tool_registry.py`，承载 `BuiltinToolSpec`、内置工具注册、启用过滤、工具目录构建与联网搜索开关
- `backend/agent/connection.py` 已从单纯 re-export 改为真实承载连接别名、默认 base URL/model 与 `get_llm()` 工厂
- `sources.py`、`prompts.py`、`history.py`、`retrieval.py` 已承载对应 source、business answer、history、KB retrieval 实现，并通过兼容测试锁定与 legacy 符号的一致性
- `backend/agent/dashboard.py` 已拆为编排入口、`dashboard_payload.py` 与 `dashboard_attachments.py`，附件解析/表格解析/fallback 仪表盘生成已迁出；`runtime_support.py` 仅 re-export dashboard 门面符号，兼容旧导入
- `backend/agent/builder_context.py` 已承载 `builder.py` 中的配置读取、任务元数据回填与 workflow 快照纯 helper；`builder_history.py` 已承载历史加载与面板历史持久化 helper；`builder_streaming.py` 已承载 wrapper 统一 `ainvoke` 与 LangGraph 流式循环；`builder_wrappers.py` 已承载 LangGraph / plain chat / function calling wrapper 适配层，`builder.py` 已降至 600 行以内
- `backend/agent/runtime_support.py` 已移除工具注册、连接工厂、source/prompt/history/retrieval、LLM helper 与 dashboard/payload/attachment fallback 重复实现；`_build_kb_timeout_fallback` 已迁至 `backend/agent/fallbacks.py`，`runtime_support.py` 仅保留兼容导入聚合
- `backend/agent/runtime_plain_chat.py` 已承载直接多模态回答、plain text chat 消息构造、工具绕过判断、plain text 超时与流式直答 helper；`runtime_support.py` 仅 re-export 这些入口，并通过兼容测试锁定旧符号身份
- `backend/agent/tools.py`、`backend/agent/runtime_tools.py`、`backend/agent/builder.py`、`backend/agent/langgraph.py` 已将 `from backend.agent.runtime_support import *` 改为按需显式导入，减少 focused modules 对兼容聚合层的反向依赖
- `backend/agent/langgraph_helpers.py` 已承载查询改写、`AgentState` 与 workflow 事件投递 helper，`langgraph.py` 已回落到 600 行以内
- 已新增 `tests/test_agent_core_split_regression.py` 拆分回归矩阵，锁定 legacy `backend.agent_core` 与拆分模块的关键入口符号身份/行为兼容，并约束 `agent_core.py`、`runtime_support.py`、`langgraph.py` 的职责边界
- 已新增 `deploy/validate_agent_core_split.py` 一键回归脚本，当前验证覆盖 183 个 agent_core/compat/orchestrator/stream 相关用例，确认拆分兼容层无行为回退

### 1.2 引入异步任务队列（P1）

当前任务中心基于内存管理，不支持持久化和分布式。

方案：

1. 引入 ARQ（基于 Redis 的轻量异步队列）作为默认任务后端
2. 保留当前内存任务管理作为开发模式 fallback
3. 配置项：`TASK_BACKEND=memory | arq`

涉及文件：

- `backend/core/task_runtime.py`
- `backend/stores/task_store.py`
- `backend/helpers/task_execution_helpers.py`
- 新增 `backend/tasks/backends.py`
- 新增 `backend/tasks/registry.py`
- 新增 `backend/tasks/worker.py`

当前实际状态说明：

- 本轮已新增 `backend/tasks/backends.py` 作为任务队列后端抽象层，集中封装 `MemoryTaskQueueBackend`、`ArqTaskQueueBackend`、`build_task_queue_backend()` 与 `dispatch_task_record()`；已拆分 `backend/tasks/registry.py`：settings 负责 env/worker 策略，health 负责 stale/queue/heartbeat health，enqueue 负责 ARQ Redis 投递；`registry.py` 保留兼容导出；`backend/tasks/worker.py` 作为持久化任务记录的 ARQ worker 入口；未发现独立 `backend/task_queue.py` 模块，当前本地后端仍沿用 `backend/core/task_runtime.py` 的 memory 后台执行路径
- 已新增 `backend/tasks/registry.py` 与 `backend/tasks/worker.py`，支持 `TASK_BACKEND=memory|arq`
- `enqueue_task` 已支持 memory 本地后台执行与 ARQ 外部队列分流，ARQ 模式会先持久化任务再投递 `run_task_by_id`
- 已支持 `ARQ_QUEUE_NAME`、`ARQ_WORKER_MAX_JOBS`、`ARQ_KEEP_RESULT_SECONDS`、`ARQ_WORKER_HEARTBEAT_KEY`、`ARQ_WORKER_HEARTBEAT_SECONDS`、`ARQ_PENDING_STALE_SECONDS`、`ARQ_RUNNING_STALE_SECONDS` 配置
- 已补充 ARQ worker heartbeat 纯函数、Redis key 生成、TTL 计算与 ARQ health check 最小接入；任务列表 payload 已增加 pending/running 滞留告警的轻量 `health` 字段，并在 `TASK_BACKEND=arq` 时补充 Redis/ARQ 真实队列长度、积压阈值与 worker heartbeat TTL 摘要
- 已补充 `ARQ_RETRY_ATTEMPTS`、`ARQ_RETRY_BACKOFF_SECONDS`、`ARQ_WORKER_DRAIN_SECONDS` 解析与 `health.runtime` / `health.summary` 摘要，统一暴露 retry/backoff、graceful drain、queue backlog、heartbeat 与 stale task 告警
- ARQ worker 启动配置已直接消费 retry/drain 语义：`max_tries`、`retry_jobs`、`job_completion_wait` 会由环境变量派生；失败任务落库为 failed 且未超过尝试次数时，会按固定 backoff 抛出 `arq.Retry` 重新入队
- ARQ worker 已增加幂等任务启动保护：pending 可启动，completed/running/waiting_approval 会跳过，failed 仅在 ARQ retry 投递且未超重试预算时再次启动
- 本轮已将 `upload_documents` 与审批恢复链路中直接调用 `asyncio.create_task` 的绕过点接入 `backend/tasks/backends.py` 的统一 `dispatch_task_record()`；`backend/routes/content_routes.py` 新增可注入 `enqueue_external_task`，`backend/core/router_registration.py` 动态解析 API 进程当前外部队列投递函数，ARQ 模式下不再在 API 进程本地 spawn
- 上传 staging 目录已共享化/可配置：`DOCUMENT_UPLOAD_STAGING_DIR` 用于 API 与 ARQ worker 共享上传 staging 文件目录，默认建议 `/app/runtime/upload_staging`
- 已新增 `deploy/compose.arq-worker.yml` 独立 worker + Redis 运维入口，并在 `docs/ARQ_WORKER_OPERATIONS.md` 记录部署、健康检查、优雅关停与任务排空演练
- 已完成生产告警模板：`deploy/alerts/insightdesk-arq-alerts.yml`，并提供 `python deploy/validate_alert_rules_static.py` 静态校验
- 已提供真实 Redis/ARQ E2E smoke drill：`python deploy/run_arq_e2e_smoke.py --timeout-seconds 90` 会用 Docker Compose 启动 Redis/ARQ worker、创建 persisted task、投递 ARQ，并轮询到 `completed`
- 关停排空演练脚本已提供：`python deploy/run_arq_drain_drill.py --timeout-seconds 120`；真实环境需执行确认

### 1.3 存储层抽象升级（P1）

在现有 Store Protocol 基础上完成 PostgreSQL 适配：

1. 在 `backend/stores/` 下新增 `pg_*.py` 适配器
2. `factory.py` 根据 `DATABASE_PROVIDER=sqlite|postgres` 切换实现
3. 向量库增加 Qdrant 适配（`backend/stores/vector_store.py` 协议 + Qdrant 实现）
4. 配置项：`VECTOR_STORE_PROVIDER=faiss | qdrant`

当前实际状态说明：

- 已新增 `backend/core/storage_runtime.py` 与 `backend/stores/vector_store.py`，支持 `VECTOR_STORE_PROVIDER=faiss|qdrant`
- `DocPipeline` 已通过 `VectorStoreAdapter` 创建/加载/保存向量库，FAISS 仍保留 Windows 非 ASCII 路径 staging 兼容
- Qdrant 模式不再要求本地 `VECTOR_STORE_PATH` 存在，加载时会连接远端 collection
- 已补充存储运行时、adapter 选择、Qdrant 远端加载、Qdrant collection 删除/清理语义与 DocPipeline 回归测试
- 已新增轻量数据校验 payload：覆盖数据库/向量库 provider 配置摘要、FAISS path/index 文件提示、Qdrant URL/collection 配置提示、delete/clear 支持声明、warnings/risks；该校验不连接真实 PostgreSQL/Qdrant
- 已补充 `validate_postgres_config()` / `validate_qdrant_config()` 纯函数，静态校验 DSN、Qdrant URL 与 collection 形态，并在 runtime summary 中返回 `invalid_config`、脱敏 DSN、warning code；测试全程离线
- 已提供迁移前配置/一致性预检脚本：`python deploy/validate_storage_migration.py --json`；该脚本不连接远端 PostgreSQL/Qdrant，只做配置校验与本地 SQLite 快照预检
- `PostgresTaskStore` 已补齐 attachment promotion 查询、按 session 删除、孤儿/过期 promotion 清理，避免 Postgres 模式回落到 SQLite 父类路径
- 已新增 `deploy/run_storage_integration_check.py` 真实环境执行契约：默认不连接外部服务，设置 `STORAGE_INTEGRATION_TEST=1` 后会检查 PostgreSQL 连接/schema readiness 与 Qdrant collections/test collection roundtrip
- 已新增真实 Qdrant env-gated 集成测试保护：测试 collection 必须使用 `insightdesk_test_` 前缀，JSON 输出包含 checked/skipped/errors/warnings、脱敏 DSN/URL 与 collection 信息；当前本机无真实服务配置时会明确 skip 或按缺配置失败

### 1.4 可观测性基础（P2）

1. 引入 `structlog` 替换标准 `logging`，统一日志格式
2. 添加 OpenTelemetry trace 到 Agent 执行路径
3. 增加 LLM 调用指标收集：Token 消耗、延迟、成功率
4. 在 `/api/operations/metrics` 暴露 Prometheus 格式指标

当前实际状态说明：

- 已抽出 `backend/core/runtime_metrics.py` 的 Prometheus 文本生成函数，operations 路由只负责鉴权和收集 payload
- `/api/operations/metrics` 已暴露 uptime、HTTP 请求/错误、状态码分组、最近错误数量、最近请求/错误时间戳
- 已暴露任务队列后端标签、任务状态动态分组与最新任务更新时间，可覆盖 `waiting_approval` 等新增状态
- 已新增进程级 LLM 调用指标，覆盖同步/流式 LLM 调用的 provider/model、成功/错误/超时、延迟与 token 用量，并接入 `/api/operations/metrics` Prometheus 输出
- 已新增 `backend/core/tracing.py` 进程内轻量 trace span helper，支持 start/end/error 生命周期事件、duration、attributes 与最近 N 条滚动保留，不引入真实 OTel exporter
- Orchestrator 的 `run_orchestrator` / `resume_orchestrator` / Agent step 已接入轻量 span，测试可证明真实 Agent 执行路径会记录 trace event
- `GET /api/operations/traces` 可查询最近 trace events，`DELETE /api/operations/traces` 可清空本地 trace 缓冲
- `GET /api/operations/traces` 已支持 `event`、`name`、`trace_id`、`span_id` 过滤，并在 summary 中回显 filters，便于运维快速定位单条链路
- 设置页 Trace 运维面板已接入上述过滤参数，可按事件类型、span 名称、trace_id、span_id 收敛本地 trace 列表
- `/api/operations/runtime` 已新增 `operations_summary`，汇总健康状态、HTTP/LLM 错误率、请求速率、活跃任务数与告警列表
- `/api/operations/metrics` 已同步暴露 `insightdesk_operations_*` Prometheus 指标，便于 dashboard/alert rule 直接消费
- 已新增 OTLP-style export payload：trace events 可转为 `resource_spans` / `resource_logs` 预览，包含 `service.name`、trace/span、duration、status 与 attributes，不引入真实网络 exporter 依赖
- 已新增跨进程观测聚合契约：`POST /api/operations/traces/ingest` 可合并外部 trace events，runtime metrics 支持按 source/process 聚合多进程 snapshot
- 已新增 operations dashboard 模板闭环：`GET /api/operations/observability` 与 traces 响应返回 `dashboard_cards`、`panel_templates`、`export_preview`，Trace 运维面板展示 OTLP 预览与 source/process 摘要

---

## 阶段二：Agent 能力升级与新 Agent 落地

目标：从单 Agent 编排演进到多 Agent 协作架构，落地核心业务 Agent。

预计周期：5-6 周

依赖：阶段一中 1.1（agent_core 拆分）完成

### 2.1 多 Agent 协作框架（P0）

#### 架构设计

```text
用户请求
  │
  ▼
┌──────────────────────────────┐
│     Orchestrator Agent       │  任务分解、Agent 调度、结果聚合
│     (编排 Agent)             │
└──────────┬───────────────────┘
           │ 分发子任务
     ┌─────┼──────┬──────────┐
     ▼     ▼      ▼          ▼
  Research  Data   Writing   QA
  Agent    Agent   Agent    Agent
```

#### 实现方案

基于 LangGraph 的 Multi-Agent 模式：

```python
# backend/agent/orchestrator.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal

class OrchestratorState(TypedDict):
    user_request: str
    plan: list[dict]              # 任务分解结果
    current_step: int
    agent_results: dict[str, Any] # 各 Agent 返回结果
    final_output: str
    needs_human_approval: bool

def build_orchestrator_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)
    graph.add_node("plan", plan_node)
    graph.add_node("route", route_to_agent_node)
    graph.add_node("research", research_agent_node)
    graph.add_node("data_analysis", data_agent_node)
    graph.add_node("writing", writing_agent_node)
    graph.add_node("review", qa_agent_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("human_gate", human_approval_node)
    # ... edges and conditional routing
    return graph.compile()
```

涉及新增文件：

- `backend/agent/orchestrator.py` — 编排图定义
- `backend/agent/registry.py` — Agent 注册和发现
- `backend/agent/protocols.py` — Agent 接口协议
- `backend/agent/state.py` — 共享状态定义

当前落地状态：

- 已完成 LangGraph 编排图、Agent 注册表、共享状态、审批暂停/恢复语义
- 已接入 `research` / `data_analysis` / `writing` / `review` / `integrator` / `general` 六类 Agent
- 已接入任务运行时与前端任务中心入口，支持多 Agent 工作流创建和审批继续
- 已新增 Agent step 级运行统计：`agent_metrics` 记录 duration、trace/span、token、成本、artifact/source 数量，`agent_cost_summary` 汇总到 workflow 状态与任务参数
- 已新增低风险并行分支调度：连续同 `parallel_group` 的 pending step 可并发执行，组内失败会记录已完成结果并停止下游
- 已新增显式 DAG 依赖建模：step 支持 `depends_on`，调度器会并发运行所有依赖满足的 ready step，并保留旧顺序/`parallel_group` 兼容语义
- 已新增并行审批批量化与失败恢复：ready approval steps 会暴露 `approval_batch`，批量 approve/reject 可一次处理；失败分支会记录 failed step、blocked downstream，独立分支继续完成
- 已补全 Provider/model token cost 映射与 trace 联动：metrics helper 支持内置价格表与 task metadata pricing override，state 增加 `trace_spans` 映射，便于 Trace UI 定位 step/span

#### Agent 注册协议

```python
# backend/agent/protocols.py

from typing import Protocol, Any

class AgentProtocol(Protocol):
    name: str
    description: str
    capabilities: list[str]

    async def execute(
        self,
        task: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def can_handle(self, task_type: str) -> bool:
        ...
```

### 2.2 数据分析 Agent（P0）

#### 业务场景

- 用户上传 Excel/CSV 后，自动识别数据结构并给出统计摘要
- 支持自然语言数据查询（"销售额最高的前 5 个地区"）
- 自动生成 ECharts 可视化配置
- 与现有 Dashboard 功能打通

#### 实现方案

```text
backend/agent/agents/
  └── data_analysis.py      当前轻量实现：结构识别、统计摘要、图表建议

后续可继续拆成：
  └── data_analyst/
      ├── agent.py          Agent 主入口
      ├── data_loader.py    Excel/CSV 文件加载与结构识别
      ├── query_engine.py   自然语言转 Pandas 查询
      ├── chart_builder.py  ECharts 配置生成
      └── summary.py        统计摘要生成
```

当前落地状态：

- 已实现 `DataAnalysisAgent`，支持从 `task.input`、`task.metadata.rows`、`context.rows`、`context.data` 读取结构化数据
- 已支持 list[dict]、二维数组、JSON/CSV 文本、本地 CSV/TSV/JSON/Excel 文件路径的数据画像
- 已输出行列数量、数值列统计、分类列 Top 值、缺失计数、预览行、query result 和 chart spec artifact
- 已支持自然语言查询：top/bottom、最高/最低、前 N、AND/OR/区间过滤、sum/avg/count 分组聚合，并可按分类维度聚合排序
- 已输出前端可识别的 `dashboard-card` Markdown 块，可复用现有 Dashboard/ECharts 渲染组件
- 已支持多 Agent 工作流 API 的 `data_files` 字段：CSV/TSV/JSON/Excel 附件可自动解析为 `context.rows`，并自动补入 `data_analysis` 步骤
- 已打通前端上传入口：CSV/TSV/JSON/Excel 附件会切换为“分析”入口，并直连多 Agent 数据分析工作流
- 已支持超大表格采样与预览：workflow 入口会限制 `context.rows` 为 500 行样本，并保留总行数/采样信息
- 已支持结构化查询配置：`task.metadata.query` / `context.data_query` 可传入嵌套 `filter_tree`，覆盖 `and/or` 条件树与 `= / != / > / >= / < / <= / in / not_in / between / contains` 操作符，并在 query result 与 metadata 中保留应用记录
- 已支持采样策略配置透传：`task.metadata.sampling`、`context.data_sampling_config` 与旧 `context.data_sampling` 会进入 profile 与执行 metadata，便于前端展示样本上限、Sheet 与总行数
- 后续优化：图表配置交互式微调、Excel 多 Sheet 选择 UI 与更丰富采样策略

核心工具：

| 工具名 | 功能 | 输入 | 输出 |
| --- | --- | --- | --- |
| `analyze_data_structure` | 识别数据结构 | 文件路径 | 列名、类型、统计概要 |
| `query_data` | 自然语言查询 | 查询文本 + 数据引用 | 查询结果 DataFrame |
| `generate_chart` | 生成图表配置 | 数据 + 图表意图 | ECharts JSON |
| `data_summary` | 生成数据摘要 | 数据引用 | Markdown 摘要 |

安全约束：

- Pandas 查询在沙箱环境执行，禁止 `exec` / `eval` / 文件系统访问
- 单次查询内存限制 512MB
- 查询超时 30 秒

### 2.3 深度研究 Agent（P0）

#### 业务场景

- 行业研究报告自动生成
- 政策追踪与合规分析
- 竞品对比分析
- 时效性信息综合研判

#### 实现方案

将 `RESEARCH_LOGIC_V2.md` 中的设计落地为独立 Agent：

```text
backend/agent/agents/
  └── researcher/
      ├── __init__.py
      ├── agent.py              Agent 主入口
      ├── intent_classifier.py  意图与范围分类（Stage 1）
      ├── plan_builder.py       研究计划构建（Stage 2）
      ├── facet_resolver.py     分面解析与模板匹配（Stage 3）
      ├── query_matrix.py       查询矩阵生成（Stage 4）
      ├── source_evaluator.py   来源归一化与分桶（Stage 6）
      ├── claim_extractor.py    原子声明提取（Stage 8）
      ├── claim_verifier.py     声明验证（Stage 9）
      ├── contradiction.py      矛盾发现与升级（Stage 10）
      ├── evidence_chain.py     声明级证据链与验证摘要（Stage 12）
      └── synthesizer.py        研究综合输出（Stage 11）
```

与现有代码的关系：

- 复用 `search_runtime/` 的搜索基础设施
- 复用 `search_runtime/types.py` 中已有的 V2 数据类型
- 替代 `search_runtime/research_service.py` 中的 V1 流程
- 保持 Quick/Deep 双模式兼容

分阶段落地：

| 子阶段 | 内容 | 周期 |
| --- | --- | --- |
| 2.3a | 意图分类 + 研究计划 + 分面解析 | 1 周 |
| 2.3b | 查询矩阵 + 来源评估 + 优先抓取 | 1.5 周 |
| 2.3c | 声明提取 + 验证 + 矛盾处理 | 2 周 |
| 2.3d | 研究综合输出 + UI 集成 | 1 周 |

当前实际状态说明：

- 已落地 `DeepResearchAgent`，支持 Quick/Deep 双模式、Provider 参数、时间范围、轮次与抓取上限配置
- 已实现意图分类、fallback 研究计划、查询矩阵、来源评估、原子声明提取、声明验证、矛盾聚合与 V2 研究 artifact
- 已新增声明级证据链：每条 claim 可追踪到候选来源、来源层级、独立来源族、证据强度、核验备注与是否需要关注
- 已在任务结果 metadata 中输出 `partial_claim_count` / `unverified_claim_count` / `contradiction_count`，便于前端和后续审计快速判断研究质量
- 已在 `research_report` v2 artifact 中新增 `delivery_quality`，汇总 claim 覆盖率、来源质量和可执行 action items
- 已在任务结果 metadata 中补充 `claim_source_coverage_ratio` / `claim_verification_ratio` / `primary_source_count` / `delivery_action_count`，便于自动化交付门禁判断
- 已在前端报告预览中接入 `claim_evidence_chains` / `claim_verification_summary`，可查看声明级证据链、核验摘要、来源层级与外链
- 引用图谱/段落定位/冲突提示 MVP 已接入：研究档案搜索/筛选、跨会话主动引用入口、专用 CitationPanel 的声明级证据展示、段落级引用定位、引用图谱摘要与冲突提示已进入前后端联调面；当前 mock/e2e 已覆盖 `/api/research/archives` 查询参数与 Research V2 档案 payload。
- 已新增 archive 级 Provider 能力声明覆盖：研究档案 payload 汇总 source 已声明的真实 provider/capabilities 元数据，便于前端和审计识别来源能力边界
- 已新增段落/claim/source 双向导航与引用图谱扩展：`paragraph_claim_links`、`navigation_index` 与 paragraph graph 节点/边进入 `/api/research/archives` payload
- 已新增跨档案冲突聚合与审校记录闭环：列表响应返回 `conflict_groups`，`POST /api/research/archives/{artifact_id}/conflict-resolutions` 可持久化冲突 resolution 并回填审校状态

### 2.4 写作 Agent（P1）

#### 实现方案

```text
backend/agent/agents/
  └── writer/
      ├── __init__.py
      ├── agent.py           Agent 主入口
      ├── outline.py         大纲生成与协商
      ├── drafter.py         分段撰写
      ├── style.py           风格模板管理
      ├── fact_checker.py    事实性验证（调用知识库）
      └── formatter.py       输出格式化（Markdown / Deck JSON）
```

写作流程：

```text
用户需求 → 大纲生成 → 用户确认/修改大纲
  → 分段撰写（每段引用知识库/研究结果）
  → 事实性验证
  → 风格校正
  → 输出（Markdown / Deck JSON / PPTX）
```

风格模板：

- `briefing` — 工作汇报型，结构化、要点式
- `research` — 研究报告型，完整论证链路
- `executive` — 高管摘要型，精炼结论导向
- `custom` — 用户自定义模板

当前实际状态说明：

- 已增强 `WritingAgent`，可从 research / data_analysis 上游 artifact、sources、metadata 中提取信息
- 已输出结构化 Markdown 交付稿，包含 Request、Executive Summary、Key Findings、Data Highlights、Evidence And Sources、Caveats And Next Steps
- 已新增多风格模板细化：`WritingAgent` 支持从 task metadata 或 context 选择 `executive_brief`、`technical_report`、`email_update`、`decision_memo`，默认模板保持兼容；输出 metadata 会记录 `template`、`style` 与 `template_sections`
- 已新增 Deck JSON 直接生成：当 task metadata 或 context 请求 `output_format=deck_json` / `delivery_format=deck` / `artifact_type=deck_json` 时，额外输出轻量 `deck_json` artifact，包含 slides、source registry、evidence refs 与生成 metadata
- 后续优化：LLM 参与的大纲协商与事实校验回路

### 2.5 质量审核 Agent（P1）

```text
backend/agent/agents/
  └── reviewer/
      ├── __init__.py
      ├── agent.py              Agent 主入口
      ├── fact_consistency.py   引用与结论一致性检查
      ├── data_accuracy.py      数字、日期、来源准确性
      ├── quality_scorer.py     输出质量评分
      └── checklist.py          检查清单管理
```

审核维度：

| 维度 | 检查内容 | 评分权重 |
| --- | --- | --- |
| 事实一致性 | 结论是否有引用支撑 | 30% |
| 数据准确性 | 数字、日期是否与来源一致 | 25% |
| 覆盖完整性 | 是否遗漏关键方面 | 20% |
| 表达质量 | 措辞是否专业、逻辑是否清晰 | 15% |
| 格式规范 | 是否符合模板要求 | 10% |

当前实际状态说明：

- 已增强 `ReviewAgent`，可输出机器可读的 `quality_gate` artifact
- 已提供 `pass / needs_fix / fail` 门禁结果、`passed` 布尔值、问题列表、检查项、阻塞问题数量
- 已新增可配置审核清单：`ReviewAgentConfig.checklist` 以及 task/context 覆盖项会进入 `quality_gate.checklist` 和 Markdown Checklist
- 已新增确定性数字/日期溯源与引用一致性基础检查：writing 输出中的数字/日期会在非 writing 上游证据中查找，带引用标记但无 sources 时会生成 `needs_fix` 级 issue
- 剩余增强：更深的引用一致性审查、人工审批联动与可配置审核策略产品化

### 2.6 人工审批门控（P1）

在 Agent 编排层增加审批检查点：

```python
# backend/agent/approval.py

APPROVAL_REQUIRED_ACTIONS = {
    "kb_modify": "知识库修改操作",
    "report_publish": "报告发布",
    "external_api_call": "外部系统调用",
    "data_export": "数据导出",
}

class ApprovalGate:
    async def check(self, action: str, context: dict) -> bool:
        if action not in APPROVAL_REQUIRED_ACTIONS:
            return True  # 自动放行
        # 创建审批请求，等待用户确认
        approval = await self.request_approval(action, context)
        return approval.approved
```

前端集成：

- 在工作流可视化中展示审批节点
- 用户可在任务中心查看待审批项
- 支持批量审批和审批策略配置

当前实际状态说明：

- 多 Agent 工作流已支持 `waiting_approval` 暂停/恢复语义，并可提交 approved/rejected 决策
- 任务中心已产品化展示 Approval gate，包含审批原因、审批专用筛选、按钮 loading/禁用态与行内错误
- 前端 mock 与 e2e 已覆盖从任务中心审批等待中的 multi-agent workflow
- 已新增 `POST /api/tasks/approvals/batch` 批量审批接口，前后端与 mock 均支持按任务独立返回成功/失败结果，任务中心已提供批量 approve/reject 控件并补充 smoke 覆盖
- 审批审计详情页/事件下钻已接入设置页安全审计明细
- 审批策略配置已接入基础运行时配置，可通过 `GET /api/tasks/approval-policy` 与 `PUT /api/tasks/approval-policy` 读取/更新 `enabled`、`required_task_types`、`high_risk_requires_approval`、`default_reviewer_role` 与 `updated_at`
- 审计留存/高级筛选已接入基础闭环：mock 与 e2e 覆盖 `category`、`user_id`、时间窗口、`action`、`result`、`limit` 明细筛选，以及 `keep_latest` / `dry_run` 留存预览和真实 cleanup 统计
- 已新增安全审计归档与合规保全后端闭环：`audit-archive-policy` 支持 preview/export 与 retention cutoff，`audit-events/legal-hold` 可按 request_id 标记 legal hold，cleanup 保留 legal hold 记录
- 已新增企业 SIEM 导出与跨租户审计报表：`audit-siem-export` 支持 JSON/NDJSON 脱敏导出，`audit-aggregate-report` 按 tenant/org/user/category/action/result 汇总

---

## 阶段三：研究管线与交付管线强化

目标：提升研究输出质量和交付产物的专业度。

预计周期：4-5 周

依赖：阶段二中 2.3（研究 Agent）基本落地

### 3.1 Research V2 完整落地（P0）

在 2.3 阶段基础上完成剩余能力：

1. Provider 能力声明机制完善
   - 每个 Provider 声明 `supports_time_range` / `supports_news_topic` / `supports_raw_content` 等
   - 运行时自动记录 Provider 限制作为研究 caveat
   - 涉及文件：`search_runtime/providers/base.py` 及各 Provider 实现

2. 声明持久化
   - Deep 模式下持久化原子声明和验证结果
   - 存入现有任务/消息结果 payload
   - 前端 CitationPanel 展示声明级别的证据链路

   当前状态：
   - 后端已在 `research_report` v2 artifact 中持久化 `atomic_claims`、`claim_verifications`、`claim_evidence_chains` 与 `claim_verification_summary`
   - 证据链已包含 claim 文本、核验状态、证据强度、候选来源、来源层级、来源族、发布时间与 caveat
   - artifact 已新增 `delivery_quality`：包含 claim 来源覆盖率、核验比例、来源层级/新鲜度/独立来源族摘要，以及补证、补主来源、处理矛盾、复核 caveat 等 action items
   - Agent metadata 已新增 `claim_source_coverage_ratio`、`claim_verification_ratio`、`primary_source_count` 与 `delivery_action_count`，可作为交付质量门禁或审计入口
   - 前端报告预览已渲染 `claim_evidence_chains`，支持查看核验摘要、声明卡片、来源展开与外链跳转
   - 专用 CitationPanel 的引用图谱/段落定位/冲突提示 MVP 已接入，支持声明级证据展示、按声明筛选入口、段落级引用链接、引用图谱摘要与冲突摘要；下一步增强正文内高亮跳转、可交互图谱与跨档案冲突审校

3. 研究档案
   - 支持研究结果作为独立 Artifact 持久化
   - 支持后续会话引用历史研究档案
   - 研究档案自动关联引用来源

   当前状态：
   - 多 Agent 工作流完成后会自动把 Research Agent 的 `research_report` v2 结果保存为 report-compatible artifact
   - 研究档案 content 已保留 `research_archive`、`research_report`、`claim_evidence_chains`、`claim_verification_summary`、sources、metadata 与关联 task_id
   - 任务参数会写回 `research_archive_artifact_id`，后续 UI 或会话可通过现有 artifact API 引用
   - 研究档案搜索/筛选与跨会话主动引用基础闭环已接入，`GET /api/research/archives` 支持 `q`、`session_id`、`task_id`、`limit` 过滤并返回 `archives`、`total`、`limit`
   - 研究档案 payload 已扩展 `paragraph_citations`、`citation_graph` 与 `conflict_summary`，`q` 搜索可命中段落、引用图谱与冲突摘要内容
   - 已新增正文段落与 claim/source 的双向跳转索引、全文级引用图谱展开/过滤、跨档案冲突聚合与冲突审校 resolution 记录，前端 Research Citation Panel 已展示图谱过滤、冲突聚合与审校状态

### 3.2 Deck 交付管线升级（P1）

按 `DECK_DELIVERY_PLAN.md` 中的方案落地结构化交付管线：

```text
来源选择 → Deck 规划 → Deck 起草 → 人工审校 → 导出渲染
```

具体任务：

1. Deck 内容与渲染分离
   - Deck JSON Schema 独立于渲染逻辑
   - 支持单页重新生成而非整体重新生成

2. 证据引用一等公民
   - 每页 Deck 关联引用来源和证据强度
   - 审校界面展示每页的引用覆盖度

   当前状态：
   - Deck 生成已能从 AIMessage 的 structured metadata 中抽取 `sources` / `claim_evidence_chains`
   - Research sources 会写入 DeckSpec `source_registry`，并转成每页 `evidence_refs`
   - 带证据的 slide 会标记为 `supported`，source registry 非空时会生成 appendix sources 页
   - DeckSpec `generation.evidence_coverage` 与导出 helper payload 已输出全局/逐页引用覆盖度统计，包括 `slides_with_evidence`、`total_evidence_refs`、`coverage_ratio` 与 `unsupported_slide_ids`
   - Deck 导出 helper 已新增 `evidence_review` 摘要，面向审校 UI 直接提供覆盖状态、待补证 slide、逐页来源标题与 action items
   - 前端 Deck 审校面板已接入 `evidence_review` 同构摘要，展示 review status、action items、待审页数量与当前页来源；后端字段缺失时会用现有 coverage / evidence refs 生成 fallback
   - Deck 内容块已写入 `evidence_ref_ids` / `evidence_source_ids` / `evidence_excerpt_ids`，前端审校面板会展示当前页每个内容块的来源绑定状态
   - PPTX 导出已对带 `evidence_refs` 的 slide 增加正文/摘要引用标识，并在证据面板使用对应编号
   - 单页重生成已在新页缺少 `evidence_refs` 时保留原页 `evidence_refs` / `quality_state`，新页提供 refs 时使用新 refs，并在替换后刷新 coverage / unsupported slide ids
   - 已新增 Deck 引用一致性校验：验证 `evidence_refs.source_id` 是否存在于 `source_registry`，以及 block `evidence_ref_ids` 是否能在所属 slide `evidence_refs` 中找到；主 helper、legacy 入口的导出/审校 payload 均会携带轻量 `citation_validation` gate 摘要
   - 前端 Deck 编辑器已展示 `citation_validation` gate 状态、导出可用性、issue 数与缺失 source/ref，smoke 用例覆盖 failed gate
   - Deck 导出前强阻断策略 MVP 已接入：`citation_validation.can_export=false` 时导出接口默认返回 409，并携带 `citation_validation`、`evidence_review` 与 `export_gate`；显式 `allow_unsafe_export=true` 可作为人工确认后的 override
   - 已新增块级引用手动调整：`PATCH /api/decks/{deck_id}/slides/{slide_id}/blocks/{block_id}/refs` 可更新 block evidence/source/excerpt refs，并刷新 `citation_validation`、`evidence_review` 与 `export_gate`
   - 已新增图表 block normalization：Deck 更新与单页替换会规范 chart block contract，写入 normalization 状态，前端 Deck 编辑器可在内容块下勾选引用并保存草稿
   - 后续优化：企业 PPTX 模板系统与 PDF 导出

3. 导出质量提升
   - PPTX 模板系统（支持企业品牌模板）
   - 图表自动嵌入 PPTX
   - PDF 导出支持

### 3.3 多模型并行对比增强（P2）

1. 后端支持同一问题并行调用多个模型
2. 答案合成逻辑：取各模型的共识要点 + 差异标注
3. 前端多面板自动对比视图优化
4. 模型性能统计（响应时间、Token 消耗、用户偏好）

当前实际状态说明：

- `/api/chat/parallel` 已支持同一问题多面板并行调用多个模型，并按 `answer_group_id` 归档同一轮回答
- 已有答案评审接口可对同一 answer group 的多模型回答打分、推荐主答案并支持一键提升推荐答案
- 本轮已增强评审 payload，新增 `consensus_points`、`difference_points` 与 `model_performance`
- 前端 `AnswerReviewModal` 已展示共识要点、独有关注点和模型表现（耗时、速度、长度、证据数）
- 已新增 token 消耗统计与合成答案：评审 payload 输出 `token_usage`、`token_summary`、`synthesis`、`synthesized_answer`，无真实 usage 时会标记 estimated 并使用确定性估算
- 已新增用户偏好信号闭环：采纳推荐答案时记录 selected/recommended/accepted/persisted 状态并写入本地 feedback 信号，前端评审弹窗展示 token、合成答案与偏好状态
- 后续优化：接入真实 LLM 参与的高级 synthesis、长期评测数据仓库与个性化偏好模型

---

## 阶段四：生产化与生态扩展

目标：将系统从"可用"提升到"可靠、可运维、可扩展"。

预计周期：4-5 周

### 4.1 MCP 连接器产品化（P0）

将 MCP 从基础骨架升级为可扩展的插件生态：

```text
mcp_servers/
  ├── knowledge_server.py     知识库 MCP（已有）
  ├── search_server.py        搜索 MCP（已有）
  ├── database_server.py      数据库查询 MCP（新增）
  ├── calendar_server.py      日历/日程 MCP（新增）
  ├── notification_server.py  通知推送 MCP（新增）
  └── custom/                 用户自定义 MCP 目录
```

连接器管理：

- 前端连接器市场 UI（已有 v1 MCP catalog）
- 连接器健康检查和状态监控
- 连接器级别的权限控制
- 连接器配置热更新

当前实际状态说明：

- `GET /api/connectors/mcp` 的 catalog payload 已增加 `enabled`、`configured`、`healthy`、`status`、`status_reasons` 与 `source`
- 已新增 `mcp_server_health_payload()` / `list_mcp_server_health()`，提供静态配置级健康检查
- catalog payload 已补充 `capability_scopes`、`risk_level`、`requires_approval` 与 `config_schema` 摘要，覆盖内置 connector 与自定义 config connector
- 已新增 `evaluate_mcp_connector_policy()` 纯函数 helper，可基于 connector payload、允许 scopes、已审批 connector 名单与高风险放行开关返回结构化 `allowed` / `requires_approval` / `reasons` 评估结果
- `select_mcp_connections()` 已接入 connector policy，运行时会按 `MCP_ALLOWED_SCOPES`、`MCP_APPROVED_CONNECTORS`、`MCP_ALLOW_HIGH_RISK` 过滤未授权/未审批连接器，catalog 同步返回 policy 结果
- 已新增 MCP connector 审批名单 helper：支持 normalize / add / remove / list，并将 `MCP_APPROVED_CONNECTORS` 与配置存储中的 runtime approval 合并为有效审批名单
- 已新增 `GET /api/connectors/mcp/approvals`、`POST /api/connectors/mcp/approvals` 与 `DELETE /api/connectors/mcp/approvals/{connector_name}`；viewer 可查看，admin 可批准/撤销，runtime approval 已持久化到 app config store 并在启动时回填
- 设置页已新增 MCP 审批面板，可查看 catalog 风险、审批来源、有效/运行时/环境变量批准，并支持 admin 在 UI 中批准或撤销 runtime approval
- 已新增 `GET /api/connectors/mcp/runtime-health` 与 `list_mcp_server_runtime_health()`，可按需启动/握手已选连接器并返回工具清单、耗时、失败原因与汇总状态，默认受 `MCP_RUNTIME_PING_TIMEOUT_SECONDS` 超时保护
- 设置页 MCP 审批面板已接入 runtime health 检查入口，可在 UI 中触发握手并查看每个连接器的状态、耗时、工具清单或错误原因
- runtime health summary 已补充结构化告警摘要：`status_counts`、`unhealthy_connectors`、`slow_connectors`、`alert_count` 与 `alerts`，便于运维直接定位失败、超时或慢连接器
- runtime health 已新增持久化历史记录，`/api/connectors/mcp/runtime-health` 返回最近握手快照、状态摘要、失败/慢连接器与耗时，历史 payload 不保留工具返回内容或敏感配置
- 已新增 `GET /api/connectors/mcp/runtime-health/history?limit=10`，可查询持久化 runtime health 历史；设置页 MCP 审批面板已接入独立刷新入口，展示状态、healthy/unhealthy 数量、告警数与连接器名称
- 已新增 `database`、`calendar`、`notification` 三个内置 MCP connector metadata、默认 stdio 连接与最小可运行 server，catalog/static health 可直接展示三类扩展连接器
- 已新增 `GET /api/connectors/mcp/config` 与 `PUT /api/connectors/mcp/config`，支持 MCP server config 热更新、敏感字段脱敏返回、保存后清理 agent cache；设置页 MCP 审批面板已接入 JSON 配置编辑与保存
- 自定义 MCP config 可通过 `metadata` 声明连接器展示信息、权限/能力范围、风险等级、审批标记与配置摘要；这些产品化字段不会传入运行时 MCP client
- 默认 MCP project root 已修正为当前项目根目录，避免内置 `mcp_servers` 路径偏到项目上一级
- 当前健康检查只校验启用状态、配置结构、本地 stdio 入口、cwd、URL 等，不启动外部 MCP server

### 4.2 身份与权限体系完善（P0）

在现有 `IDENTITY_AND_ORGS.md` 基础上完成：

1. 资源级权限绑定
   - 会话、知识库、Artifact、Deck 绑定 `org_id`
   - 路由层 helpers 强制资源归属检查

2. 完整 RBAC
   - 角色：`owner` / `admin` / `editor` / `viewer`
   - 每种角色的操作矩阵文档化

3. SSO 集成预留
   - OAuth 2.0 / OIDC 对接接口
   - Token 与外部身份映射

当前实际状态说明：

- 资源级权限绑定已提前落地，并已覆盖 `workspace`、`session`、`deck`、`artifact`、`task`
- 角色模型 `owner / admin / editor / viewer` 已用于身份与资源授权
- 前端管理页已支持组织、用户、成员关系与资源授权维护
- SSO/OIDC 已补充安全配置查询、加密持久化配置编辑、授权 URL/PKCE 启动入口、callback 授权码交换与 ID token 验证、已验证 claims 到本地身份/成员关系的同步路径、短期应用会话 token 签发、SQLite 持久化会话存储，以及设置页配置与登录入口
- SSO login/callback 审计已记录 `state`、`nonce`、应用 session token 的短指纹，以及角色、组数量、成员关系数量、token 类型与过期信息；原始敏感值不进入审计日志
- 统一操作矩阵与权限审计动作目录已后端化
- 已补齐安全审计汇总闭环：`GET /api/security/audit-summary?category=access|identity|auth` 可按 `action` / `result` 聚合权限、身份与 SSO 审计事件，并返回最近事件数量；响应保持脱敏边界，不暴露 secret/token
- 设置页已新增“安全审计”汇总入口，接入分类筛选、窗口大小、刷新、`action` / `result` / `category` 聚合视图，并补充 Playwright smoke 覆盖
- 设置页安全审计明细已接入审批审计详情页/事件下钻，可查看审批动作事件
- 设置页安全审计留存/高级筛选已接入基础闭环，覆盖分类/用户/时间窗口等明细筛选，以及留存 dry-run preview 与真实 cleanup 统计；剩余增强主要是长期归档、企业 SIEM 导出与合规保全
- 已补充针对设置页 SSO 配置保存与 OIDC 登录入口的端到端 UI 回归；剩余增强主要是企业 IdP 实测、更多浏览器与 callback 场景覆盖，而非核心后端能力缺口

### 4.3 部署与运维增强（P1）

1. Docker Compose 多服务拆分
   - 独立 API 服务、Worker 服务、向量库服务
   - 健康检查端点 `/healthz` 和 `/readyz`

2. Kubernetes 部署支持
   - Helm Chart
   - HPA 配置
   - PersistentVolumeClaim 模板

3. 配置热更新
   - 模型配置和搜索配置支持运行时更新
   - 无需重启服务

4. 优雅关停
   - 收到 SIGTERM 后等待活跃任务完成
   - 流式连接优雅断开

当前实际状态说明：

- Docker Compose MVP 已完成第一轮拆分：默认服务名调整为 `api`，异步任务使用 `worker` + `redis` 的 `tasks` profile，Qdrant 使用 `storage` profile
- `api` 已使用现有 `/api/health` 做 Compose 容器健康检查，并等待 `ollama` 健康后启动；同时已新增 `/healthz` 与 `/readyz` 供 Kubernetes / 运维探针使用，其中 `/readyz` 仅做本地配置与运行时轻检查；`redis` 使用 `redis-cli ping`，`qdrant` 使用 `/readyz`，`postgres` 使用 `pg_isready`
- `worker` 已强制 `TASK_BACKEND=arq`，并通过 `depends_on` 等待 `redis` / `ollama` 健康；worker 容器健康检查覆盖 Redis 连通性，并已接入可配置 ARQ health check 心跳键与 pending/running 滞留阈值解析
- `.env.example` 已补充 Compose 专用的 `DOCKER_REDIS_URL`、`DOCKER_QDRANT_URL`、`DOCKER_DATABASE_URL`、端口与 ARQ worker 参数
- 已新增 `docs/DEPLOYMENT_OPERATIONS.md`，说明 API、ARQ worker、Redis、Qdrant 的环境变量、启动命令、任务滞留告警 payload 与静态校验命令
- 已新增 Helm MVP 骨架 `deploy/helm/insightdesk`，覆盖 API Deployment/Service、可选 ARQ worker、ConfigMap、runtime PVC、HPA、探针与 NOTES，并提供 `deploy/validate_helm_static.py` 静态校验
- 已为 Helm API / worker Deployment 增加 `terminationGracePeriodSeconds` 与 `preStop` lifecycle，静态校验脚本已将优雅关停字段纳入 chart 契约
- 已新增可选 API `PodDisruptionBudget`，支持通过 `podDisruptionBudget.enabled=true` 在集群维护或滚动升级时保护 API 可用副本
- 已新增 Helm NetworkPolicy 与配置热更新契约：`networkPolicy.enabled` 控制 API/worker/Redis/Qdrant/Postgres 策略，Deployment 支持 `checksum/config` 触发配置变更滚动更新
- 已补齐 Helm lint/template CI 静态契约与 ARQ 关停排空说明：静态校验覆盖 NetworkPolicy、PDB、preStop、terminationGracePeriodSeconds；ARQ runbook 明确 Kubernetes SIGTERM、preStop、drain timeout 的协同关系
- 已新增 Qdrant env-gated 集成测试契约：只有设置 `QDRANT_INTEGRATION_TEST=1` 与 `QDRANT_URL` 时才运行真实连接测试，默认明确 skip

### 4.4 外部系统集成 Agent（P2）

```text
backend/agent/agents/
  └── integrator/
      ├── __init__.py
      ├── agent.py            Agent 主入口
      ├── connectors/
      │   ├── base.py         Connector 配置描述与敏感字段脱敏
      │   ├── feishu.py       飞书集成
      │   ├── dingtalk.py     钉钉集成
      │   ├── email.py        邮件集成
      │   └── webhook.py      通用 Webhook
      ├── sync.py             定时数据同步
      └── push.py             结果推送
```

当前实际状态说明：

- 已落地 `IntegratorAgent` 后端 MVP，并注册到默认 / runtime Agent registry
- Orchestrator 已能通过 `integration` / `push` / `send` / `sync` / `webhook` / `email` / `feishu` / `dingtalk` 等关键词路由到 `IntegratorAgent`
- 已支持 `webhook` / `email` / `feishu` / `dingtalk` 四类配置级 connector 描述，敏感字段仅以脱敏形式进入 artifact
- 已支持按 connector id、名称或类型选择 connector；未配置或未匹配 connector 时返回结构化错误 artifact
- 已支持 `push` / `sync` 两类 dry-run 结果 artifact，仅描述 `would_send` / `would_sync`，不进行真实外发
- 已增强真实 webhook 执行可靠性：默认仍为 dry-run 且必须显式打开 `execute`；真实执行支持可配置 retry attempts / backoff 与 connector 级 timeout override（非法 timeout 会阻断外发），artifact 与 result metadata 输出尝试次数、是否耗尽、最终状态和实际 webhook timeout，响应摘要会按 connector settings 中的 secret/token/Authorization 等敏感值做脱敏
- 已补充真实 webhook HMAC 签名：connector settings 可配置 `hmac_secret` / `signing_secret` / `signature_secret` / `webhook_hmac_secret`，默认生成 `X-Integrator-Signature: sha256=<digest>`，支持 `sha1` / `sha256` / `sha512` 与自定义签名头；签名仅在显式真实外发时生效，dry-run 默认行为不变
- 已新增真实 webhook 外发审计：每次显式外发都会生成 `integration_outbound_audit` artifact，并写入 `integrator.webhook_outbound` 结构化日志；审计 payload 只保留 connector 基础信息、endpoint fingerprint、payload summary、响应摘要、重试与签名摘要，不落原始 secret
- 已接入真实 webhook 审批门控：显式 `execute=true` 仍必须命中已启用且已审批的 webhook connector；仅配置 URL 不再允许真实外发，阻断结果会返回结构化 `approval_gate`
- 已新增 Integrator connector 配置 API：`GET /api/integrations/connectors` 返回脱敏 connector 配置，`PUT /api/integrations/connectors` 加密持久化 webhook/email/feishu/dingtalk connector，并在保存后清理 Agent cache；多 Agent 工作流运行时会从配置存储加载 connector 注入 `IntegratorAgent`
- 设置页已新增 Integrations 配置面板，支持查看、新增、编辑、启用/审批、删除和保存 Integrator connector；保存后沿用后端脱敏响应展示，避免 URL/token/secret 明文回显
- 已新增 Integrator connector 连接测试 dry-run：`POST /api/integrations/connectors/test` 会执行类型、启用、审批、endpoint/收件人/应用标识等静态检查，返回脱敏 connector、结构化 checks 与 summary；设置页 Integrations 面板已接入 `Test` 按钮，测试过程不会发出真实外部请求
- 已新增 Integrator outbound audit 持久化与查询/留存：真实 webhook 外发会写入独立 SQLite 审计表；`GET /api/integrations/audit` / `GET /api/integrations/outbound-audit` 返回脱敏审计事件，`POST /api/integrations/outbound-audit/cleanup` 支持 dry-run 与保留最近 N 条；设置页 Integrations 面板已展示最近审计记录并支持刷新
- 已新增 Integrator 定时同步调度配置 MVP：`GET/PUT /api/integrations/schedules` 加密持久化并脱敏返回 schedule；`POST /api/integrations/schedules/{schedule_id}/trigger` 支持 dry-run 触发预览，并可在 `dry_run=false` 时分发 `multi_agent_workflow`；设置页 Integrations 面板已支持 schedule 查看、新增、编辑、保存与手动触发
- 已新增无常驻线程的 Integrator scheduler tick：`POST /api/integrations/schedules/tick` 可扫描 enabled 且到期的 schedule，默认 dry-run 返回 due 列表和 would-create-task，`dry_run=false` 时批量更新运行状态并入队 `multi_agent_workflow`；设置页已补充 `interval_minutes` 编辑、字段级 cron/interval 校验和 scheduler 状态展示
- 已新增 Integrator 轻量 cron 语义：后端支持 5 段 cron 的 `*`、`*/n`、数字、列表、范围与范围步进，保存时校验字段范围，`next_run_at` 和 trigger 后推进会优先按 cron 计算；前端校验规则已与后端常见格式对齐
- 已新增默认关闭的 Integrator 后台常驻调度 worker：`INTEGRATOR_SCHEDULER_ENABLED=false` 默认不启动，启用后按 `INTEGRATOR_SCHEDULER_INTERVAL_SECONDS=60` 周期调用现有 tick/trigger/enqueue 路径，使用简单 lock 避免并发 tick，异常只记录不终止进程，应用 shutdown 时会取消后台任务
- 已补齐 Integrator cron 命名别名与时区语义：后端支持 `JAN-DEC`、`SUN-SAT` 大小写不敏感别名，并支持别名列表、范围与范围步进；`timezone` 会按 IANA timezone 校验，空值稳定归一为 `UTC`，cron `next_run_at` 会按 schedule 本地时间匹配后转回 epoch；前端同步支持别名校验、timezone datalist、保存归一与展示
- 已新增 Integrator connector 凭据轮换与 static dry-run 探活：`POST /api/integrations/connectors/{connector_id}/credentials/rotate` 仅接受 `settings` / `credentials` patch，保留 redacted 旧值并返回脱敏 `rotated_fields` / `preserved_fields`；`POST /api/integrations/connectors/{connector_id}/probe` 复用静态检查并明确不发外部请求；设置页已新增安全 JSON patch 轮换区、Probe 按钮、结果摘要与脱敏展示
- 已新增 Integrator connector 字段化凭据轮换表单：设置页支持 Token、API key、OAuth client、Basic auth、Authorization header 快速模板，并保留 JSON patch 高级模式；提交后清空敏感输入，mock 与 e2e 覆盖不泄漏
- 已新增 Integrator connector controlled external probe 后端模式：`POST /api/integrations/connectors/{connector_id}/probe` 默认仍为 static，只有显式 `mode=external` 才对已启用、已审批、HTTPS、公网 webhook 发送一次受超时保护的探活请求，并写入脱敏 outbound audit
- 已加固 Integrator connector external probe 重定向与前端显式入口：external probe 使用 no-redirect webhook client，3xx 不会自动跳转到未验证目标；设置页新增 external opt-in、timeout 输入、outbound 提示和脱敏 probe 详情展示，默认仍为 static probe
- 已补齐 Integrator cron 扩展与 DST 去重：后端支持 `@hourly` / `@daily` / `@weekly` / `@monthly` / `@yearly` / `@annually` / `@midnight` 宏与 day-of-month/day-of-week 的 `?` 字段，前端同步校验和提供轻量 presets；cron 触发推进会跳过与 `last_triggered_at` 相同的本地年月日时分，避免 DST 回拨重复本地时间二次执行

---

## 新增文件与目录总览

```text
backend/
  ├── agent/                           # 阶段一：核心拆分
  │   ├── __init__.py
  │   ├── connection.py
  │   ├── tools.py
  │   ├── retrieval.py
  │   ├── prompts.py
  │   ├── sources.py
  │   ├── history.py
  │   ├── dashboard.py
  │   ├── llm.py
  │   ├── executor.py
  │   ├── orchestrator.py              # 阶段二：多 Agent 编排
  │   ├── registry.py
  │   ├── protocols.py
  │   ├── state.py
  │   ├── approval.py
  │   └── agents/                      # 阶段二：各业务 Agent
  │       ├── data_analyst/
  │       ├── researcher/
  │       ├── writer/
  │       └── reviewer/
  ├── tasks/                           # 阶段一：异步任务队列
  │   ├── worker.py
  │   └── registry.py
  └── stores/
      ├── pg_config_store.py           # 阶段一：PostgreSQL 适配
      ├── pg_security_audit_store.py
      ├── vector_store.py              # 向量库协议
      └── qdrant_store.py              # Qdrant 适配

mcp_servers/
  ├── database_server.py               # 阶段四：新增 MCP
  ├── calendar_server.py
  ├── notification_server.py
  └── custom/

frontend/src/
  ├── components/
  │   ├── agents/                      # Agent 状态面板（新增）
  │   │   ├── AgentStatusPanel.tsx
  │   │   └── ApprovalDialog.tsx
  │   ├── data/                        # 数据分析组件（新增）
  │   │   ├── DataPreview.tsx
  │   │   ├── QueryBuilder.tsx
  │   │   └── ChartConfigurator.tsx
  │   └── research/
  │       ├── ResearchMetaCard.tsx      # 已有
  │       ├── ClaimCard.tsx            # 声明卡片（新增）
  │       └── EvidenceChain.tsx        # 证据链路（新增）
  └── stores/
      ├── agentStore.ts                # Agent 状态管理（新增）
      └── dataStore.ts                 # 数据分析状态管理（新增）
```

---

## 里程碑与时间线

```text
Week 0-1    ┃ 阶段一启动
            ┃ ├─ agent_core.py 拆分（P0）
            ┃ └─ 可观测性基础搭建开始
            ┃
Week 2-3    ┃ 阶段一收尾
            ┃ ├─ agent_core.py 拆分完成，全量测试通过
            ┃ ├─ 异步任务队列 MVP
            ┃ └─ 存储层 PostgreSQL 适配开始
            ┃
Week 4      ┃ 阶段二启动
            ┃ ├─ 多 Agent 协作框架搭建
            ┃ ├─ Agent 注册协议定义
            ┃ └─ 数据分析 Agent 骨架
            ┃
Week 5-6    ┃ 核心 Agent 开发
            ┃ ├─ 数据分析 Agent 完成
            ┃ ├─ 深度研究 Agent Phase 1（意图 + 计划 + 分面）
            ┃ └─ 人工审批门控 MVP
            ┃
Week 7-8    ┃ 研究 Agent 深化
            ┃ ├─ 深度研究 Agent Phase 2（声明 + 验证 + 矛盾）
            ┃ ├─ 写作 Agent 骨架
            ┃ └─ 质量审核 Agent 骨架
            ┃
Week 9      ┃ 阶段二收尾 + 阶段三启动
            ┃ ├─ 所有 Agent 基础功能可用
            ┃ ├─ 编排 Agent 串联各子 Agent
            ┃ └─ Research V2 完整管线联调
            ┃
Week 10-11  ┃ 交付管线强化
            ┃ ├─ Deck 交付管线升级
            ┃ ├─ 多模型并行对比增强
            ┃ └─ 声明持久化与研究档案
            ┃
Week 12-13  ┃ 阶段三收尾 + 阶段四启动
            ┃ ├─ MCP 连接器产品化
            ┃ ├─ 身份权限体系完善
            ┃ └─ 部署方案升级
            ┃
Week 14-16  ┃ 生产化收尾
            ┃ ├─ Kubernetes 部署支持
            ┃ ├─ 外部系统集成 Agent
            ┃ ├─ 端到端回归测试
            ┃ └─ 文档更新与发布准备
```

---

## 测试策略

### 新增测试要求

每个新模块必须配套以下测试：

| 测试类型 | 覆盖要求 | 位置 |
| --- | --- | --- |
| 单元测试 | 每个公共函数 | `tests/test_agent_*.py` |
| 集成测试 | Agent 端到端执行 | `tests/integration/test_*_agent.py` |
| 协作测试 | 多 Agent 编排流程 | `tests/integration/test_orchestrator.py` |
| 性能测试 | 延迟和 Token 消耗 | `tests/perf/test_*_perf.py` |

### 回归保护

- 阶段一拆分期间，每次迁移后运行全量 54 个现有测试
- 新 Agent 不得破坏现有对话流程
- 搜索 Provider 测试使用 mock，避免外部依赖

---

## 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| agent_core 拆分引入回归 | 中 | 高 | 逐函数迁移 + 每步全量测试 |
| 多 Agent 编排延迟过高 | 中 | 中 | 设置 Agent 级别超时 + 降级策略 |
| Research V2 LLM 调用成本飙升 | 中 | 中 | 严格预算控制 + Quick/Deep 模式分离 |
| PostgreSQL 迁移数据丢失 | 低 | 高 | 迁移脚本 + 数据校验 + 回滚方案 |
| MCP 连接器安全漏洞 | 中 | 高 | 沙箱执行 + 连接器权限隔离 |

---

## 成功标准

### 阶段一完成标准

- `agent_core.py` 已拆分为兼容入口 + focused agent modules，核心拆分产物均控制在 600 行以内
- 全部 54 个测试通过，无行为变更
- 异步任务队列 MVP 可运行

### 阶段二完成标准

- 数据分析 Agent 可处理 Excel/CSV 并生成图表
- 深度研究 Agent 可完成分面研究并输出结构化报告
- 编排 Agent 可串联至少两个子 Agent 完成复合任务
- 人工审批门控可在 UI 中操作

### 阶段三完成标准

- Research V2 Deep 模式可产出带声明验证的研究简报
- Deck 交付管线支持单页重新生成和证据引用
- 研究档案可持久化并在后续会话中引用

### 阶段四完成标准

- Docker Compose 多服务部署可运行
- 完整 RBAC 权限体系可用
- 至少 3 个 MCP 连接器可用
- 端到端回归测试全部通过

---

## 相关文档

- [AGENT_AND_WORKFLOW.md](./AGENT_AND_WORKFLOW.md) — 当前 Agent 模式与工作流参考
- [RESEARCH_LOGIC_V2.md](./RESEARCH_LOGIC_V2.md) — 研究管线 V2 设计
- [PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md) — 产品路线图
- [DECK_DELIVERY_PLAN.md](./DECK_DELIVERY_PLAN.md) — 交付管线规划
- [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md) — 后端分层架构
- [STORAGE_RUNTIME.md](./STORAGE_RUNTIME.md) — 存储层设计
- [IDENTITY_AND_ORGS.md](./IDENTITY_AND_ORGS.md) — 身份与权限
