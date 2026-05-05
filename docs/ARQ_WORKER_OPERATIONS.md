# ARQ Worker Operations Runbook

This runbook covers the standalone ARQ worker path used when API task submission is configured with `TASK_BACKEND=arq`.

## Deployment Contract

The API process and every worker process must share these values:

```dotenv
TASK_BACKEND=arq
REDIS_URL=redis://localhost:6379/0
ARQ_QUEUE_NAME=insightdesk:tasks
ARQ_WORKER_MAX_JOBS=4
ARQ_KEEP_RESULT_SECONDS=3600
ARQ_RETRY_ATTEMPTS=3
ARQ_RETRY_BACKOFF_SECONDS=15
ARQ_WORKER_HEARTBEAT_KEY=insightdesk:tasks:worker:heartbeat
ARQ_WORKER_HEARTBEAT_SECONDS=30
ARQ_WORKER_DRAIN_SECONDS=30
ARQ_PENDING_STALE_SECONDS=600
ARQ_RUNNING_STALE_SECONDS=1800
ARQ_QUEUE_WARNING_LENGTH=100
DOCUMENT_UPLOAD_STAGING_DIR=/app/runtime/upload_staging
TASK_STORE_FAIL_INCOMPLETE_ON_START=false
```

The repository default remains `TASK_BACKEND=memory` unless `TASK_BACKEND=arq`
is explicitly set. The planned default switch is guarded by
`TASK_BACKEND_SWITCH_READY=1` and should only happen after the ARQ long-running
validation, the drain drill report, and the ops readiness real-environment
checks are all closed.

`ARQ_QUEUE_NAME` is the hard boundary between producers and workers. A mismatch means the API can enqueue tasks successfully while workers watch a different Redis queue.

`ARQ_WORKER_DRAIN_SECONDS` maps to ARQ `job_completion_wait`. Keep the container stop grace period greater than this value so `SIGTERM` gives the worker time to stop accepting new work and finish the current job.

`DOCUMENT_UPLOAD_STAGING_DIR` must point to the same mounted directory in the API container and every worker container. For the default container layout, mount the same runtime volume at `/app/runtime/upload_staging` and set `DOCUMENT_UPLOAD_STAGING_DIR=/app/runtime/upload_staging` in both processes. This lets `upload_documents` jobs handed to an external worker read the files staged by the API process.

Workers must set `TASK_STORE_FAIL_INCOMPLETE_ON_START=false`. The API creates persisted `pending` records before enqueueing ARQ jobs; if a worker opens the SQLite task store with the default startup cleanup behavior, it can mark API-enqueued `pending` or `running` tasks as `failed` before the worker executes them.

## Standalone Compose

Use the standalone worker compose file when operating a worker outside the main application stack:

```bash
docker compose -f deploy/compose.arq-worker.yml up --build -d redis arq-worker
docker compose -f deploy/compose.arq-worker.yml ps
docker compose -f deploy/compose.arq-worker.yml logs -f arq-worker
```

If the API runs in a different stack, point it at the same Redis instance and queue:

```dotenv
TASK_BACKEND=arq
REDIS_URL=redis://localhost:6379/0
ARQ_QUEUE_NAME=insightdesk:tasks
```

For Compose-internal networking use `DOCKER_REDIS_URL=redis://redis:6379/0`. For a host Redis use `DOCKER_REDIS_URL=redis://host.docker.internal:6379/0`.

When document uploads are enabled, API and worker services must also share the same `runtime/upload_staging` volume path. Staged upload files are temporary handoff artifacts; successful and failed upload tasks clean up their staged files after the task reaches a terminal outcome.

## Health Checks

The Compose health check verifies Redis TCP connectivity from the worker container. This catches the most common deployment failure before jobs start piling up.

Runtime health should also be checked from the API task listing response:

```bash
curl "http://localhost:8000/api/tasks?limit=20"
```

Expected ARQ health signals:

- `health.runtime.backend` is `arq`.
- `health.runtime.queue_name` matches `ARQ_QUEUE_NAME`.
- `health.runtime.worker.drain.drain_seconds` matches `ARQ_WORKER_DRAIN_SECONDS`.
- `health.queue.heartbeat.present` is `true` after the worker has started.
- `health.summary.worker_heartbeat_enabled` is `true`.

The heartbeat key defaults to `insightdesk:tasks:worker:heartbeat`. Its TTL should refresh roughly every `ARQ_WORKER_HEARTBEAT_SECONDS`.

### Production Alerts

The production alert template at `deploy/alerts/insightdesk-arq-alerts.yml` can be wired into Prometheus/Alertmanager to monitor ARQ queue backlog, stale tasks, and worker heartbeat signals.

Before applying alert rule changes, run the static validator:

```bash
python deploy/validate_alert_rules_static.py
```

## E2E Smoke Drill

Run this drill after changing ARQ worker, Redis, task-store, or Compose wiring:

```bash
python deploy/run_arq_e2e_smoke.py --timeout-seconds 90
```

The drill requires Docker, and the Docker daemon must be running and reachable. It starts Redis and the ARQ worker with Docker Compose, creates a persisted task inside the container, enqueues it through ARQ, and polls until the task reaches `completed`. A successful run prints that the task completed. If it fails or times out, inspect the worker logs:

```bash
docker compose -f deploy/compose.arq-worker.yml logs arq-worker
```

When Docker CLI exists but the daemon is unavailable, the drill reports the
blocker as `docker_daemon_unavailable`. To include a non-executed Docker
Desktop/daemon start command contract in JSON output, add
`--docker-start-hint`.

To persist smoke evidence for rollout review:

```bash
python deploy/run_arq_e2e_smoke.py --timeout-seconds 90 --json --report-path runtime/ops-readiness/arq/arq-long-running-smoke.json --archive-dir runtime/ops-readiness/arq/archive --history-path runtime/ops-readiness/arq/history.json --docker-start-hint --skip-if-unavailable
```

`--skip-if-unavailable` is intended for CI or review machines without a real
Docker environment. It exits successfully with `skipped=true`,
`skipped_no_real_environment`, and the blocker detail in the JSON evidence
instead of pretending the real drill ran.

## Long-Running Validation

Use the env-gated sustained execution loop before changing the production
backend default or redispatching high-volume task traffic:

```bash
$env:ARQ_LONG_RUNNING_TEST="1"
python deploy/run_arq_long_running_validation.py --duration-seconds 900 --json --report-path runtime/ops-readiness/arq/arq-long-running-validation.json --archive-dir runtime/ops-readiness/arq/archive --history-path runtime/ops-readiness/arq/history.json --docker-start-hint --skip-if-unavailable
```

The script is intentionally inert until `ARQ_LONG_RUNNING_TEST=1` is present.
It spins the worker stack, runs repeated ARQ probe iterations, and emits a
machine-readable report for long-run closure review. The report includes a
`closure` summary, `completed_iterations`, the evidence `decision`, and an
`archive_path` when `--archive-dir` is supplied.
If the Docker daemon is unreachable, the report records
`docker_daemon_unavailable` plus the optional Docker Desktop/daemon start
command contract when `--docker-start-hint` is provided.

## Graceful Shutdown Drill

Run this drill before promoting a worker deployment change:

```bash
python deploy/run_arq_drain_drill.py --timeout-seconds 120 --json --report-path runtime/ops-readiness/arq/arq-drain-drill.json --archive-dir runtime/ops-readiness/arq/archive --history-path runtime/ops-readiness/arq/history.json --docker-start-hint --skip-if-unavailable
```

The drain drill requires Docker, and the Docker daemon must be running and reachable. It uses the ARQ E2E probe flow to enqueue a task, wait for worker pickup, stop the worker through Compose, and confirm the task reaches a terminal state without duplicate execution.
The JSON report captures the task id, each Compose step, the final terminal-state outcome, whether cleanup restored the stack, any blockers such as `docker_daemon_unavailable`, and optional Docker Desktop/daemon start commands. `--archive-dir` writes timestamped drill reports with `archive_path` embedded in the archived JSON, and `--history-path` appends the latest closure summary for audit history.

Manual fallback steps:

1. Start API, Redis, and at least one ARQ worker with the same `ARQ_QUEUE_NAME`.
2. Submit a long-running task and confirm it appears in `/api/tasks`.
3. Stop one worker with a normal Compose stop:

```bash
docker compose -f deploy/compose.arq-worker.yml stop arq-worker
```

4. Confirm the stop takes less than `ARQ_WORKER_STOP_GRACE_PERIOD` and at least `ARQ_WORKER_DRAIN_SECONDS` is available for the current job to finish.
5. Start the worker again:

```bash
docker compose -f deploy/compose.arq-worker.yml up -d arq-worker
```

6. Re-check `/api/tasks?limit=20`. There should be no duplicate completed task execution. Failed records may retry only inside `ARQ_RETRY_ATTEMPTS`.

## Emergency Drain

To drain workers without accepting more work:

```bash
docker compose -f deploy/compose.arq-worker.yml stop arq-worker
```

Wait until `health.queue.length` is stable or zero, then scale/start replacement workers with the same `ARQ_QUEUE_NAME`.

Do not change `ARQ_QUEUE_NAME` during a drain. If a queue name must change, first drain the old queue to zero, then deploy API and workers with the new queue name together.

## Default Backend Switch Contract

Changing the production default from memory to ARQ requires the explicit gate
`TASK_BACKEND_SWITCH_READY=1`.

The switch contract is considered closed only when:

- `TASK_BACKEND=arq` works in the intended deployment path.
- `deploy/run_arq_long_running_validation.py --duration-seconds 900 --json` has
  a passing real-environment report.
- `deploy/run_arq_drain_drill.py --timeout-seconds 120 --json --report-path ...`
  produces a successful closure report.
- `deploy/run_ops_readiness.py --include-real --json` shows no remaining ARQ
  real-environment blockers and lists the ARQ report paths under
  `summary.arq_report_paths`.
- `summary.task_backend_default_switch.decision` is
  `eligible_for_arq_default`. If the gate is set before the ARQ evidence files
  are present, passed, and not skipped, readiness records
  `blocked_until_arq_evidence_closes` and blocks
  `task_backend_default_switch_contract`.

## Kubernetes Shutdown Contract

For Helm deployments, keep the worker shutdown window aligned across ARQ and
Kubernetes:

```yaml
worker:
  terminationGracePeriodSeconds: 60
  lifecycle:
    preStop:
      exec:
        command: ["sh", "-c", "sleep 5"]

config:
  arqWorkerMaxJobs: "4"
  arqKeepResultSeconds: "3600"
```

The expected shutdown sequence is:

1. Kubernetes starts pod termination and runs `preStop`.
2. Endpoint removal begins while `preStop` gives the control plane a short buffer.
3. Kubernetes sends `SIGTERM` to the ARQ worker process.
4. ARQ stops taking new jobs and waits up to `ARQ_WORKER_DRAIN_SECONDS` /
   `job_completion_wait` for the current job.
5. Kubernetes sends `SIGKILL` only after `terminationGracePeriodSeconds` expires.

Keep `terminationGracePeriodSeconds` greater than `ARQ_WORKER_DRAIN_SECONDS`
plus the `preStop` sleep. During maintenance, drain workers before changing
`ARQ_QUEUE_NAME`, Redis URL, or task-store persistence settings.

## Helm Static Operations Checks

Run these checks before merging deployment changes:

```bash
python deploy/validate_helm_static.py
pytest tests/test_deploy_helm_static.py tests/test_arq_worker_ops_static.py
```

The static contract verifies that Helm still contains API/worker Deployments,
PodDisruptionBudget support, NetworkPolicy support, `preStop`,
`terminationGracePeriodSeconds`, and ConfigMap checksum rollout annotations.
