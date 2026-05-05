# 部署与运维 MVP

本文记录 Docker Compose 方式下的 API、ARQ worker、Redis、Qdrant 启动方式与关键环境变量。

## 服务拓扑

| 服务 | 默认启动 | profile | 说明 | 健康检查 / 依赖 |
| --- | --- | --- | --- | --- |
| `api` | 是 | 无 | FastAPI + 静态前端入口 | Compose 继续使用 `GET /api/health`；K8s/运维探针可使用 `GET /healthz` 与 `GET /readyz`；启动仍等待 `ollama` 健康 |
| `worker` | 否 | `tasks` | ARQ 异步任务 worker | 等待 `redis` 与 `ollama` 健康，容器内检查 Redis TCP |
| `redis` | 否 | `tasks` | ARQ 队列后端 | `redis-cli ping` |
| `qdrant` | 否 | `storage` | 可选远端向量库 | `GET /readyz` |
| `postgres` | 否 | `storage` | 预留元数据存储服务 | `pg_isready` |
| `ollama` | 是 | 无 | 本地模型服务 | `ollama list` |

## 环境变量

### API

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_PORT` | `8000` | API 暴露到宿主机的端口 |
| `TASK_BACKEND` | `memory` | `memory` 本地后台执行；`arq` 投递到 Redis/worker |
| `APP_DB_PATH` | `/app/runtime/chat_history.db` | Compose 容器内 SQLite 路径 |
| `VECTOR_STORE_PROVIDER` | `faiss` | `faiss` 或 `qdrant` |
| `DOCKER_QDRANT_URL` | `http://qdrant:6333` | Compose 内访问 Qdrant 的地址 |
| `DOCKER_OLLAMA_BASE_URL` | `http://ollama:11434` | Compose 内访问 Ollama 的地址 |

### ARQ worker / Redis

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TASK_BACKEND` | `memory` | API 使用 worker 时设为 `arq` |
| `DOCKER_REDIS_URL` | `redis://redis:6379/0` | Compose 内 Redis DSN |
| `REDIS_URL` | 空 | 本地非 Compose 运行时可设为 `redis://localhost:6379/0` |
| `ARQ_QUEUE_NAME` | `insightdesk:tasks` | API 与 worker 必须一致 |
| `ARQ_WORKER_MAX_JOBS` | `4` | 单 worker 并发任务数 |
| `ARQ_KEEP_RESULT_SECONDS` | `3600` | ARQ 任务结果保留秒数 |
| `ARQ_RETRY_ATTEMPTS` | `3` | ARQ 任务失败策略摘要使用的总尝试次数，包含首次执行；设为 `0`、`1`、`false`、`off`、`disabled` 可在 health payload 中标记 retry 关闭 |
| `ARQ_RETRY_BACKOFF_SECONDS` | `15` | ARQ retry 摘要使用的固定退避秒数；设为 `0`、`false`、`off`、`disabled` 表示不配置退避 |
| `ARQ_WORKER_HEARTBEAT_KEY` | `insightdesk:tasks:worker:heartbeat` | worker 写入 Redis 的运维心跳键；设为 `disabled` 可停用本项目自定义心跳配置并回落 ARQ 默认 |
| `ARQ_WORKER_HEARTBEAT_SECONDS` | `30` | ARQ health check 写入间隔；设为 `0`、`false`、`off`、`disabled` 可停用本项目自定义心跳配置并回落 ARQ 默认 |
| `ARQ_WORKER_DRAIN_SECONDS` | `30` | worker drain / graceful shutdown 摘要窗口秒数；设为 `0`、`false`、`off`、`disabled` 可在 health payload 中标记 drain 关闭 |
| `ARQ_PENDING_STALE_SECONDS` | `600` | pending 任务超过该秒数仍未运行时，在任务 health payload 中输出告警；设为 `0`、`false`、`off`、`disabled` 可关闭 |
| `ARQ_RUNNING_STALE_SECONDS` | `1800` | running 任务超过该秒数未更新时，在任务 health payload 中输出告警；设为 `0`、`false`、`off`、`disabled` 可关闭 |
| `ARQ_QUEUE_WARNING_LENGTH` | `100` | Redis/ARQ 队列长度超过该值时，在任务 health payload 的 `queue` 字段输出 `arq_queue_backlog`；设为 `0`、`false`、`off`、`disabled` 可关闭长度告警 |
| `TASK_STORE_FAIL_INCOMPLETE_ON_START` | `false` | worker 必须设为 `false`，避免打开 SQLite task store 时把 API 已入队的 `pending`/`running` 任务标记为 `failed` |

### Qdrant

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VECTOR_STORE_PROVIDER` | `faiss` | 使用 Qdrant 时设为 `qdrant` |
| `DOCKER_QDRANT_URL` | `http://qdrant:6333` | Compose 内 Qdrant URL |
| `QDRANT_URL` | 空 | 本地非 Compose 运行时可设为 `http://localhost:6333` |
| `QDRANT_API_KEY` | 空 | 使用托管 Qdrant 时填写 |
| `QDRANT_COLLECTION` | `insightdesk_kb` | 知识库向量 collection |

## 常用命令

### 校验 Compose 配置

```bash
docker compose config
docker compose --profile tasks --profile storage config
```

### Storage migration preflight

```bash
python deploy/validate_storage_migration.py --json
```

This preflight does not connect to remote PostgreSQL or Qdrant. It only validates storage-related configuration and inspects the local SQLite snapshot before migration rollout.

### 启动默认 API

```bash
copy .env.example .env
docker compose up --build -d api
docker compose ps
```

健康检查：

```bash
curl http://localhost:8000/api/health
```

Kubernetes / 运维探针：

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

`/healthz` 仅表示 API 进程存活；`/readyz` 只做本地配置与运行时轻量检查，不连接 Ollama、Redis、Qdrant 等重型外部服务，避免探针和测试被外部依赖抖动影响。Compose healthcheck 仍保持 `/api/health`，兼容现有部署。

### 启动 API + Redis + ARQ worker

`.env` 中设置：

```dotenv
TASK_BACKEND=arq
ARQ_QUEUE_NAME=insightdesk:tasks
ARQ_RETRY_ATTEMPTS=3
ARQ_RETRY_BACKOFF_SECONDS=15
ARQ_WORKER_HEARTBEAT_KEY=insightdesk:tasks:worker:heartbeat
ARQ_WORKER_HEARTBEAT_SECONDS=30
ARQ_WORKER_DRAIN_SECONDS=30
ARQ_PENDING_STALE_SECONDS=600
ARQ_RUNNING_STALE_SECONDS=1800
TASK_STORE_FAIL_INCOMPLETE_ON_START=false
# Compose 内部保持服务名地址
# DOCKER_REDIS_URL=redis://redis:6379/0
```

启动：

```bash
docker compose --profile tasks up --build -d api redis worker
docker compose logs -f worker
```

worker 必须设置 `TASK_STORE_FAIL_INCOMPLETE_ON_START=false`。API 会先创建持久化 `pending` 任务再投递 ARQ；如果 worker 启动时清理 incomplete task，可能把 API 已入队但尚未执行的任务提前标记为 `failed`。

ARQ E2E smoke drill：

```bash
python deploy/run_arq_e2e_smoke.py --timeout-seconds 90
```

该演练需要 Docker，且 Docker daemon 必须可用；脚本会用 docker compose 启动 Redis/ARQ worker，创建 persisted task、投递 ARQ，并轮询到 `completed`。成功时会看到 task completed；失败或超时时优先查看 worker logs：

```bash
docker compose -f deploy/compose.arq-worker.yml logs arq-worker
```

ARQ drain drill：

```bash
python deploy/run_arq_drain_drill.py --timeout-seconds 120
```

该演练同样需要 Docker daemon 可用；脚本会投递任务、等待 worker 接手、通过 Compose 停止 worker，并确认 drain/关停期间任务不会重复执行。

本地非 Compose worker 示例：

```powershell
$env:TASK_BACKEND = "arq"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:ARQ_QUEUE_NAME = "insightdesk:tasks"
arq backend.tasks.worker.WorkerSettings
```

worker 心跳检查：

```bash
arq --check backend.tasks.worker.WorkerSettings
```

默认心跳键为 `insightdesk:tasks:worker:heartbeat`，TTL 约为 `ARQ_WORKER_HEARTBEAT_SECONDS + 1` 秒。该键用于外部监控判断 worker 是否持续运行；不代表任务没有滞留，滞留/积压告警仍需结合队列长度、任务状态更新时间和业务 SLA 单独配置。

任务滞留/积压轻量告警：

```bash
curl "http://localhost:8000/api/tasks?limit=20"
```

返回体会在现有 `tasks` 列表旁追加 `health` 字段：

```json
{
  "health": {
    "enabled": true,
    "warning_count": 1,
    "pending_warning_count": 1,
    "running_warning_count": 0,
    "thresholds": {
      "pending_stale_seconds": 600,
      "running_stale_seconds": 1800
    },
    "warnings": [
      {
        "code": "task_pending_stale",
        "severity": "warning",
        "task_id": "task-id",
        "task_type": "generate_report",
        "status": "pending",
        "threshold_seconds": 600,
        "stale_seconds": 720.0
      }
    ],
    "queue": {
      "enabled": true,
      "status": "ok",
      "queue_name": "insightdesk:tasks",
      "length": 3,
      "warning_length": 100,
      "warning_count": 0,
      "warnings": [],
      "heartbeat": {
        "enabled": true,
        "key": "insightdesk:tasks:worker:heartbeat",
        "ttl_seconds": 29,
        "present": true,
        "expected_ttl_seconds": 31
      }
    },
    "runtime": {
      "backend": "arq",
      "queue_name": "insightdesk:tasks",
      "retry": {
        "enabled": true,
        "attempts": 3,
        "max_retries": 2,
        "backoff_seconds": 15,
        "strategy": "fixed"
      },
      "worker": {
        "max_jobs": 4,
        "keep_result_seconds": 3600,
        "drain": {
          "enabled": true,
          "graceful_shutdown": true,
          "drain_seconds": 30,
          "job_completion_wait_seconds": 30
        }
      }
    },
    "summary": {
      "status": "warning",
      "warning_count": 1,
      "stale_warning_count": 1,
      "queue_warning_count": 0,
      "warning_codes": ["task_pending_stale"],
      "retry_enabled": true,
      "worker_drain_enabled": true,
      "worker_heartbeat_enabled": true
    }
  }
}
```

`health.warning_*` 仍基于 API 可见的任务记录做轻量判断：`pending` 使用 `created_at` 计算排队等待时间，`running` 使用 `updated_at` 判断长时间无进展。`TASK_BACKEND=arq` 时，`health.queue` 会尝试读取 Redis 中真实 ARQ 队列长度，并检查 worker heartbeat key 的存在状态与 TTL；Redis 不可用时该字段返回 `status=unavailable`，不会阻断任务列表接口。`health.runtime` 只来自环境变量解析，不连接 Redis，可用于确认 retry attempts/backoff、worker heartbeat 与 drain/graceful shutdown 摘要；`health.summary` 会把 stale task、queue backlog、worker heartbeat missing 等告警码统一汇总。
Production alert rules live at `deploy/alerts/insightdesk-arq-alerts.yml`; validate them before rollout with `python deploy/validate_alert_rules_static.py`.

### 启动 API + Qdrant

`.env` 中设置：

```dotenv
VECTOR_STORE_PROVIDER=qdrant
QDRANT_COLLECTION=insightdesk_kb
# Compose 内部保持服务名地址
# DOCKER_QDRANT_URL=http://qdrant:6333
```

启动：

```bash
docker compose --profile storage up --build -d api qdrant
docker compose ps qdrant
```

健康检查：

```bash
curl http://localhost:6333/readyz
```

### Helm graceful shutdown

The Helm chart now exposes graceful shutdown controls for API and worker pods:

```yaml
api:
  terminationGracePeriodSeconds: 30
  lifecycle:
    preStop:
      exec:
        command: ["sh", "-c", "sleep 5"]

worker:
  terminationGracePeriodSeconds: 60
  lifecycle:
    preStop:
      exec:
        command: ["sh", "-c", "sleep 5"]
```

`terminationGracePeriodSeconds` leaves a SIGTERM drain window for uvicorn / ARQ worker.
The short `preStop` sleep gives Kubernetes time to remove the pod from Service endpoints before it exits.
Production deployments should still tune these values together with ingress timeout and queue-drain policy.

Static check:

```bash
python deploy/validate_helm_static.py
```

### Ops readiness real-environment probes

Use the readiness report before running production-only ARQ and Kubernetes
drills:

```bash
python deploy/run_ops_readiness.py --include-real --json
```

The report still lists missing environment gates such as
`ARQ_LONG_RUNNING_TEST=1` and `OPS_REAL_CLUSTER_TEST=1`, but it now also
distinguishes installed CLIs from usable local runtime access:

- `docker_daemon_unavailable` means `docker` is on PATH, but `docker info` could
  not reach the Docker daemon. Start Docker Desktop or the host Docker service
  before running ARQ smoke, long-running validation, or drain drills.
- `kubectl_current_context_missing` means `kubectl` is on PATH, but
  `kubectl config current-context` did not return a selected context. Select the
  intended production or staging context before enabling
  `OPS_REAL_CLUSTER_TEST=1`.

Both probes are non-destructive. They do not start Compose services, create
cluster resources, or connect to PostgreSQL/Qdrant.

### Kubernetes rollout drill

The real-cluster rollout/config reload drill is env-gated and inert by default:

```bash
python deploy/run_k8s_rollout_drill.py --json
```

Without `OPS_REAL_CLUSTER_TEST=1`, the command writes a JSON report with
`status=skipped` and `missing_env:OPS_REAL_CLUSTER_TEST`; it does not invoke
`helm` or `kubectl`. The local evidence contract supports the same
`--report-path`, `--archive-dir`, and `--history-path` pattern used by the ARQ
and storage drills, plus `--manifest-path` for the evidence manifest. Inert
validation can still produce attachable evidence without a cluster.

Run it only after selecting the target kube context:

```bash
kubectl config current-context
$env:OPS_REAL_CLUSTER_TEST="1"
python deploy/run_k8s_rollout_drill.py --namespace default --release insightdesk --json --report-path runtime/ops-readiness/k8s/k8s-real-cluster-probe.json --archive-dir runtime/ops-readiness/k8s/archive --history-path runtime/ops-readiness/k8s/history.json --manifest-path runtime/ops-readiness/k8s/evidence-manifest.json
```

When enabled, the runner executes `helm template`, `kubectl config
current-context`, namespace/deployment probes, and `kubectl rollout status` for
the API deployment. Add `--include-worker` when the release has
`worker.enabled=true`. The default report path is
`runtime/k8s-rollout-drill-report.json`; ops readiness passes explicit
`runtime/ops-readiness/k8s/*.json` paths and exposes them in its summary for the
rollout record.

The report now carries three review contracts:

- `contracts.real_cluster`: records `OPS_REAL_CLUSTER_TEST`, required tools
  (`helm`, `kubectl`), safe skip behavior, and the evidence paths.
- `contracts.config_reload.hot_reload_checklist`: records the Helm config
  reload strategy, ConfigMap checksum rollout, optional mounted config path,
  and `CONFIG_HOT_RELOAD_*` fields.
- `contracts.graceful_shutdown.graceful_shutdown_checklist`: records API and
  worker termination grace periods, `preStop` delay, and deployment template
  lifecycle wiring.

`--manifest-path` writes a compact evidence manifest with the generated
rollout steps, checklist contracts, report path, archive path, and history
path. Attach it to the 4.3 real-cluster validation closure alongside the
detailed report JSON.

### Helm disruption budget

Set `podDisruptionBudget.enabled=true` to create an API `PodDisruptionBudget`:

```bash
helm template insightdesk deploy/helm/insightdesk --set podDisruptionBudget.enabled=true
```

The default `minAvailable: 1` protects at least one API pod during voluntary disruptions such as node drain or rolling maintenance.

## 当前边界

- Compose MVP 继续复用现有 `/api/health`；独立 `/healthz` 与 `/readyz`
  已供 Kubernetes / 运维探针使用。
- `worker` 健康检查覆盖 Redis 连通性、ARQ worker 心跳、Redis 队列长度、
  pending/running 滞留告警与 drain / graceful shutdown 摘要；生产告警仍应
  接入外部监控系统。
- Qdrant 已具备 Compose 服务、健康检查、真实迁移/回滚演练入口与证据契约；
  生产环境复跑和 collection 生命周期清理属于非阻塞增强。
- Kubernetes、Helm、HPA、PVC、优雅关停与配置热更新已具备静态验证、演练入口
  和证据契约；真实集群复跑仍由 `OPS_REAL_CLUSTER_TEST=1` 门控，作为部署审批
  或环境准入动作执行。
