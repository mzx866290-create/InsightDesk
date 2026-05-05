# Validation

## Scope

This document consolidates the smoke checklist and release validation notes into one place.

## Final Acceptance Entry

Use the final validation runner as the release gate index:

```bash
venv312\Scripts\python.exe deploy/run_final_validation.py --profile quick
venv312\Scripts\python.exe deploy/run_final_validation.py --profile quick --parallel-workers 4
venv312\Scripts\python.exe deploy/run_final_validation.py --profile full --include-frontend-build
```

The quick profile covers the implementation-plan marker check, agent core split
regression, storage/orchestrator contracts, Helm static validation, the inert
storage probe, and frontend type checking. The full profile adds the broader
delivery-agent contract set and the production frontend build. The production
build gate also rejects release-introduced chunk-size warnings.

Use `--parallel-workers` for local quick or CI capacity where independent
validation steps can run concurrently. `--fail-fast` keeps execution serial so
the first failing gate is still reported deterministically.

By default, command stdout/stderr in the human and JSON reports is truncated to
keep release-gate logs compact. Truncation affects captured stdout/stderr only;
step status and failure-pattern detection remain unchanged. Use verbose output
only when diagnosing a specific failing gate:

The runner also normalizes subprocess output for stable local and CI logs: it
requests non-colored command output with `NO_COLOR=1`, `FORCE_COLOR=0`, and
`TERM=dumb`, then strips any remaining ANSI escape sequences before reporting,
truncation, JSON serialization, and failure-pattern checks.

Execution reports include a compact `summary` block with pass/fail counts, so CI
and release notes can read the gate outcome without scanning individual step
results. Human output also prints a single-line summary such as
`summary: selected=6 executed=6 passed=6 failed=0 skipped=0 truncated_steps=0 output_failure_steps=0 fail_fast_stopped=false`.
Executed reports show each step's `duration_ms` plus aggregate timing in the
summary; list-only reports keep the same summary semantics without per-step
execution timing. Failure-pattern matching still uses the full normalized output
before report truncation.

```bash
venv312\Scripts\python.exe deploy/run_final_validation.py --profile quick --verbose-output
```

To keep truncation enabled but raise the per-stream output budget:

```bash
venv312\Scripts\python.exe deploy/run_final_validation.py --profile full --include-frontend-build --max-output-chars 12000
```

To inspect the selected gate without executing commands:

```bash
venv312\Scripts\python.exe deploy/run_final_validation.py --profile quick --list --json
```

### Optional Environment Gates

The storage integration probe is inert by default:

```bash
venv312\Scripts\python.exe deploy/run_storage_integration_check.py --compact
```

Run the same probe against real PostgreSQL/Qdrant targets only after setting
the target environment:

```bash
$env:STORAGE_INTEGRATION_TEST="1"
$env:DATABASE_URL="postgresql://..."
$env:QDRANT_URL="http://localhost:6333"
venv312\Scripts\python.exe deploy/run_storage_integration_check.py
```

To persist local rollout evidence without changing the gate behavior, pass the
report contract paths:

```bash
venv312\Scripts\python.exe deploy/run_storage_integration_check.py --report-path runtime/ops-readiness/storage/storage-real-integration.json --archive-dir runtime/ops-readiness/storage/archive --history-path runtime/ops-readiness/storage/history.json --manifest-path runtime/ops-readiness/storage/evidence-manifest.json
```

### Ops Readiness Closure

Use the ops readiness report to track the production-only drills that cannot be
closed by unit tests alone:

```bash
venv312\Scripts\python.exe deploy/run_ops_readiness.py --json
venv312\Scripts\python.exe deploy/run_ops_readiness.py --include-real --json
venv312\Scripts\python.exe deploy/run_ops_readiness.py --run-safe --json
```

Default mode excludes real Redis/ARQ, PostgreSQL, Qdrant, and Kubernetes
execution. `--include-real` reports the missing tools and environment gates for
those drills. `--run-safe` executes only local non-invasive checks such as
storage preflight, Helm static validation, and quick release validation.

When real drills are included, the readiness report also runs non-destructive
local probes for required CLIs:

- Docker checks `docker info --format "{{json .ServerVersion}}"`; if the CLI is
  installed but the daemon is unreachable, the blocker is
  `docker_daemon_unavailable`.
- Kubernetes checks `kubectl config current-context`; if no current context is
  configured, the blocker is `kubectl_current_context_missing`.

These probes do not start containers, mutate Kubernetes resources, or connect to
application data stores. They only make the report distinguish "command exists"
from "real target is usable enough to attempt the drill."

For ARQ real-environment checks, readiness also threads the intended evidence
paths into each command and into `summary.arq_report_paths`:

```text
runtime/ops-readiness/arq/arq-long-running-smoke.json
runtime/ops-readiness/arq/arq-long-running-validation.json
runtime/ops-readiness/arq/arq-drain-drill.json
runtime/ops-readiness/arq/history.json
runtime/ops-readiness/arq/evidence-manifest.json
```

The ARQ drill runners support `--archive-dir` for timestamped reports,
`--history-path` for the rolling drill history, `--manifest-path` for the shared
handoff manifest, and `--docker-start-hint` for a non-executed Docker
Desktop/daemon start command contract. When Docker CLI is present but the daemon
is down, reports use the blocker `docker_daemon_unavailable`.

Storage readiness uses the same evidence pattern for preflight, real migration,
real integration, rollback plan, and real rollback checks. The paths are exposed
in `summary.storage_report_paths`, `summary.storage_archive_dir`, and
`summary.storage_report_history_path`; the unified handoff manifest is exposed
as `summary.storage_evidence_manifest_path`:

```text
runtime/ops-readiness/storage/storage-migration-preflight.json
runtime/ops-readiness/storage/storage-real-migration.json
runtime/ops-readiness/storage/storage-real-integration.json
runtime/ops-readiness/storage/storage-rollback-plan.json
runtime/ops-readiness/storage/storage-real-rollback.json
runtime/ops-readiness/storage/history.json
runtime/ops-readiness/storage/evidence-manifest.json
```

These JSON files are local evidence artifacts only. They do not enable
PostgreSQL/Qdrant connections; the existing environment gates still control real
migration, integration, and rollback execution.

Kubernetes rollout readiness now uses the same local evidence contract. The
readiness report threads paths into the K8s drill commands and exposes them in
`summary.k8s_report_paths`, `summary.k8s_archive_dir`, and
`summary.k8s_report_history_path`:

```text
runtime/ops-readiness/k8s/k8s-real-cluster-probe.json
runtime/ops-readiness/k8s/k8s-config-reload-drill.json
runtime/ops-readiness/k8s/history.json
```

These paths do not bypass `OPS_REAL_CLUSTER_TEST`; without that gate the K8s
runner remains inert and does not invoke `helm` or `kubectl`.

`deploy/run_ops_readiness.py --json` also returns a top-level
`evidence_manifest` object. It groups the ARQ, Storage, and K8s evidence
contracts into `areas.arq`, `areas.storage`, and `areas.k8s`, including each
area's manifest path, archive directory, history path, report paths, checklist,
required report fields, blockers, and remaining real-environment drills. This
manifest is safe to generate before the deployment window because it does not
execute real Docker, PostgreSQL, Qdrant, or Kubernetes actions unless the
corresponding real-environment gates are enabled.

The ARQ long-running validation is a real Docker drill and is inert by default:

```bash
$env:ARQ_LONG_RUNNING_TEST="1"
venv312\Scripts\python.exe deploy/run_arq_long_running_validation.py --duration-seconds 900 --json --report-path runtime/ops-readiness/arq/arq-long-running-validation.json --archive-dir runtime/ops-readiness/arq/archive --history-path runtime/ops-readiness/arq/history.json --manifest-path runtime/ops-readiness/arq/evidence-manifest.json --docker-start-hint
```

The ARQ drain drill now emits a closure report that should be attached to the
rollout record:

```bash
venv312\Scripts\python.exe deploy/run_arq_drain_drill.py --timeout-seconds 120 --json --report-path runtime/ops-readiness/arq/arq-drain-drill.json --archive-dir runtime/ops-readiness/arq/archive --history-path runtime/ops-readiness/arq/history.json --manifest-path runtime/ops-readiness/arq/evidence-manifest.json --docker-start-hint
```

Keep the task backend default as `memory` until
`TASK_BACKEND_SWITCH_READY=1` is approved and the persisted ops evidence shows
the ARQ long-running validation plus drain drill closed for the target
environment. Readiness uses those archived reports for
`summary.task_backend_default_switch.decision`, so a local shell does not need
to re-run the gated drills just to confirm `eligible_for_arq_default`.

For Kubernetes rollout closure, set `OPS_REAL_CLUSTER_TEST=1` only against the
target cluster. The readiness report then includes the real cluster probe and
the config reload rollout drill. Helm also exposes an optional mounted config
file contract via `config.hotReload.enabled`; the default release-safe strategy
remains `config.reloadStrategy=rolloutOnConfigChange`.

The dedicated drill runner is safe to call in default validation because it
skips without the real-cluster gate:

```bash
venv312\Scripts\python.exe deploy/run_k8s_rollout_drill.py --json --report-path runtime/ops-readiness/k8s/k8s-real-cluster-probe.json --archive-dir runtime/ops-readiness/k8s/archive --history-path runtime/ops-readiness/k8s/history.json --manifest-path runtime/ops-readiness/k8s/evidence-manifest.json
```

Expected default result: `status=skipped`,
`blockers=["missing_env:OPS_REAL_CLUSTER_TEST"]`, and no `helm`/`kubectl`
commands executed. For real closure, select the kube context first, set
`OPS_REAL_CLUSTER_TEST=1`, then run:

```bash
venv312\Scripts\python.exe deploy/run_k8s_rollout_drill.py --namespace default --release insightdesk --json --report-path runtime/ops-readiness/k8s/k8s-real-cluster-probe.json --archive-dir runtime/ops-readiness/k8s/archive --history-path runtime/ops-readiness/k8s/history.json --manifest-path runtime/ops-readiness/k8s/evidence-manifest.json
```

The JSON report records `helm template`, kube context, namespace/deployment
probes, and `kubectl rollout status`. Use `--include-worker` only for releases
deployed with `worker.enabled=true`.

### Evidence Closure Verification

Use the real ops evidence runner as the single closure entry for ARQ, Storage,
and K8s production evidence. The default `--json` mode is a dry-run plan: it
reads the ops readiness `real_environment` checks, reports what would run, and
does not execute real Redis/ARQ, PostgreSQL, Qdrant, Docker, Helm, or
Kubernetes actions. Dry-run mode may still persist the plan and report artifacts
when report paths are supplied:

```bash
venv312\Scripts\python.exe deploy/run_real_ops_evidence.py --json
venv312\Scripts\python.exe deploy/run_real_ops_evidence.py --json --skip-probes
venv312\Scripts\python.exe deploy/run_real_ops_evidence.py --json --report-path runtime/ops-readiness/real-ops/real-ops-evidence-plan.json --archive-dir runtime/ops-readiness/real-ops/archive --history-path runtime/ops-readiness/real-ops/history.json
```

Use `--skip-probes` only for fast local validation. It skips live Docker and
Kubectl probes while preserving static env/tool checks. Do not use it for the
target-environment strict preflight or execution.

For real closure, run it only in the approved target environment. `--execute`
is the explicit execution gate; without it the runner must remain inert.
Use `--strict-plan` before either dry-run or execution when the selected
`real_environment` checks must be actionable before continuing. Strict plan mode
returns non-zero when the selected checks have a blocker, an unknown readiness
state, or an empty selection. Use `--strict-verifier` when the same invocation
should finish by enforcing the strict evidence verifier. If any selected
`real_environment` check is blocked, the runner executes zero drills rather than
doing a partial run:

```bash
venv312\Scripts\python.exe deploy/run_real_ops_evidence.py --json --strict-plan --report-path runtime/ops-readiness/real-ops/real-ops-evidence-plan.json --archive-dir runtime/ops-readiness/real-ops/archive --history-path runtime/ops-readiness/real-ops/history.json
venv312\Scripts\python.exe deploy/run_real_ops_evidence.py --json --execute
venv312\Scripts\python.exe deploy/run_real_ops_evidence.py --json --execute --strict-plan --strict-verifier --report-path runtime/ops-readiness/real-ops/real-ops-evidence-report.json --archive-dir runtime/ops-readiness/real-ops/archive --history-path runtime/ops-readiness/real-ops/history.json
```

The report, history, and archive records must include `mode`, `execute`,
`strict_plan`, `summary`, `plan`, `results`, and `verifier` so dry-run planning
and executed closure evidence use the same audit shape.

After real closure evidence has been generated, use the evidence closure
verifier to check whether ARQ, Storage, and K8s production evidence is closed
before a release is promoted:

```bash
venv312\Scripts\python.exe deploy/verify_ops_evidence.py --json
venv312\Scripts\python.exe deploy/verify_ops_evidence.py --json --strict
```

The default mode reports the evidence closure status without failing when
artifacts or real-environment signals are still missing. Use `--strict` only
for the final delivery gate, where any unresolved ARQ, Storage, or K8s
evidence should fail the validation step.

## Pre-Release Checks

### Environment

- backend starts
- frontend starts
- model endpoint is reachable
- `.env` is configured

### Core Functional Checks

- health endpoint works
- single-panel chat works
- multi-panel chat works
- retrieval works
- attachment upload works
- session memory works
- task center updates work
- deck/report generation works

### Mode Checks

- local + langgraph
- cloud + function_calling
- auto mode routing

### Delivery Checks

- report generation
- deck export
- download filename behavior
- shared links if enabled

## Regression Baseline

Run:

```bash
venv312\Scripts\python.exe -m pytest -q
cd frontend && npm run build
```

## Security Regression

Validate:

- remote protected routes require a configured API token
- frontend protected flows automatically send the browser-saved API token
- weak remote share secret is rejected
- response security headers are present

## Recommended Release Rule

Only treat a build as demo-ready when:

- backend tests pass
- frontend build passes
- at least one local end-to-end manual flow is verified
