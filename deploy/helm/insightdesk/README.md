# InsightDesk Helm MVP

This chart is a minimal Kubernetes deployment skeleton for InsightDesk. It is
intended to be small, reviewable, and statically verifiable before adding
cluster-specific production features.

## Included Resources

- API `Deployment` and `Service`.
- API startup/liveness probes on `/healthz` and readiness on `/readyz`.
- `ConfigMap` for core runtime settings.
- Optional ARQ worker `Deployment` with Redis-heartbeat startup/readiness probes.
- Optional import of sensitive environment variables from a pre-created
  Kubernetes `Secret` through `secret.existingSecret`.
- Service exposure guard: `NodePort` and `LoadBalancer` require
  `service.allowExternal=true`; the default remains `ClusterIP`.
- Service-account token automount and Kubernetes service-link environment
  injection are disabled by default.
- Optional runtime `PersistentVolumeClaim` mounted at `/app/runtime`.
- Optional API `HorizontalPodAutoscaler` with `autoscaling.enabled=true`.
- Optional API `PodDisruptionBudget` with `podDisruptionBudget.enabled=true`.
- Optional `NetworkPolicy` resources for API, worker, Redis, Qdrant, and
  PostgreSQL with `networkPolicy.enabled=true`.
- Config changes trigger a rolling restart when
  `config.reloadStrategy=rolloutOnConfigChange`.

## API Readiness

`/healthz` reports only that the API process is alive. `/readyz` performs a
short SQLite/PostgreSQL query, validates runtime wiring, and checks Redis/ARQ
queue connectivity when `TASK_BACKEND=arq`. It deliberately does not probe
Ollama, Qdrant, or the worker heartbeat. A required dependency failure returns
HTTP 503 and removes the API Pod from Service endpoints. Worker Pods use their
separate Pod-unique Redis heartbeat probes.

## Static Validation

Run the repository-local checks without Helm or Kubernetes:

```bash
python deploy/validate_helm_static.py
pytest tests/test_deploy_helm_static.py
```

If Helm is installed, run the additional rendering checks:

```bash
helm lint deploy/helm/insightdesk
helm template insightdesk deploy/helm/insightdesk
helm template insightdesk deploy/helm/insightdesk --set worker.enabled=true --set autoscaling.enabled=true
helm template insightdesk deploy/helm/insightdesk --set podDisruptionBudget.enabled=true
helm template insightdesk deploy/helm/insightdesk --set worker.enabled=true --set networkPolicy.enabled=true
helm template insightdesk deploy/helm/insightdesk --set secret.existingSecret=insightdesk-runtime
```

## Secret Management

The chart intentionally does not create a `Secret` from Helm values. Plaintext
secret values passed with `--set` or committed in a values file can be retained
in shell history, CI logs, and Helm release history.

Create the Secret separately, preferably through an external-secret controller,
sealed-secret workflow, or a protected environment file:

```bash
kubectl create secret generic insightdesk-runtime \
  --from-env-file=/secure/path/insightdesk.env \
  --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install insightdesk deploy/helm/insightdesk \
  --set secret.existingSecret=insightdesk-runtime
```

Secret keys are imported as environment variables and should use the names the
application already consumes, such as:

- `DATABASE_URL` or `POSTGRES_DSN`
- `REDIS_URL`, `ARQ_REDIS_DSN`, or `ARQ_REDIS_PASSWORD`
- `QDRANT_API_KEY`
- `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and `TAVILY_API_KEY`
- `APP_AUTH_TOKENS_JSON`, `SHARE_LINK_SECRET`, and `OIDC_CLIENT_SECRET`

`DATABASE_URL` and `REDIS_URL` are no longer rendered into the ConfigMap. For an
unauthenticated in-cluster Redis, use the non-sensitive
`config.arqRedisHost`, `config.arqRedisPort`, and `config.arqRedisDatabase`
settings. Existing deployments that used `config.databaseUrl` or
`config.redisUrl` must migrate those values to a Secret; rendering fails with a
clear message instead of silently exposing or ignoring the credential.
Known sensitive names are also rejected when supplied through `env[].value`;
use `secret.existingSecret` or `env[].valueFrom.secretKeyRef` instead.
The chart also rejects `TASK_BACKEND`, `POD_NAME`, and
`ARQ_WORKER_HEARTBEAT_KEY` in `env[]`. These variables control workload routing
or Pod-specific worker health and must remain under chart control; configure
the API task backend with `config.taskBackend`.

After rotating an externally managed Secret, restart both workloads because
environment variables are only read when containers start:

```bash
kubectl rollout restart deployment/insightdesk-api
kubectl rollout restart deployment/insightdesk-worker
```

## Service Exposure

The default Service is internal-only `ClusterIP`. Exposing it through a
`NodePort` or cloud load balancer requires an explicit acknowledgement:

```bash
helm upgrade --install insightdesk deploy/helm/insightdesk \
  --set service.type=LoadBalancer \
  --set service.allowExternal=true \
  --set 'service.loadBalancerSourceRanges[0]=203.0.113.0/24'
```

Use authentication, TLS termination, and restrictive source ranges before
enabling external access. Prefer a separately managed Ingress/Gateway when the
cluster already has a standard edge-security layer.

## NetworkPolicy

Network policies are disabled by default so the chart remains safe to render in
clusters without a NetworkPolicy controller. Enable them explicitly:

```bash
helm template insightdesk deploy/helm/insightdesk --set worker.enabled=true --set networkPolicy.enabled=true
```

The default policy set models these paths:

- Same-namespace API ingress on port `8000`.
- API and worker egress to Redis `6379`, Qdrant `6333`, and PostgreSQL `5432`.
- Redis, Qdrant, and PostgreSQL ingress from API and worker pods.
- Worker ingress is an empty list by default.

Override `networkPolicy.*.ingress`, `networkPolicy.*.egress`, and
`networkPolicy.dependencies.*.podSelector` when the dependency pods use
cluster-specific labels.

## Config Rollout

`config.reloadStrategy=rolloutOnConfigChange` adds a ConfigMap checksum to the
API and worker pod templates. Kubernetes rolls pods when rendered configuration
changes, which gives deterministic config refresh without requiring a live
reload endpoint inside the app.

The real-cluster drill report also includes a `hot_reload_checklist` under
`contracts.config_reload`. It records the default strategy, checksum rollout
annotation, optional mounted ConfigMap path, and `CONFIG_HOT_RELOAD_*` report
fields used for evidence review.

## Graceful Shutdown

The API and worker deployments expose `terminationGracePeriodSeconds` and
`lifecycle.preStop` controls through `values.yaml`. The real-cluster drill
report includes `contracts.graceful_shutdown.graceful_shutdown_checklist` so
reviewers can verify the chart applies the configured drain windows and
pre-stop delay before the rollout evidence is archived.

The default API and worker commands use `exec`, so Uvicorn and ARQ receive
`SIGTERM` directly. Each worker Pod uses its own ARQ Redis heartbeat key for
startup and readiness, so replicas cannot mask one another. It intentionally
has no Redis-backed liveness probe: a Redis outage
should make the worker unready, not cause a cluster-wide restart loop. Process
exit is still handled by the container runtime and Deployment restart policy.

## Real-Cluster Evidence

The Kubernetes rollout drill is inert unless `OPS_REAL_CLUSTER_TEST=1` is set:

```bash
python deploy/run_k8s_rollout_drill.py --json
```

Without the gate, the command writes a skipped JSON report and does not call
`helm` or `kubectl`. With the gate enabled, use explicit evidence paths:

```bash
python deploy/run_k8s_rollout_drill.py --namespace prod --release insightdesk --json --report-path runtime/ops-readiness/k8s/k8s-real-cluster-probe.json --archive-dir runtime/ops-readiness/k8s/archive --history-path runtime/ops-readiness/k8s/history.json --manifest-path runtime/ops-readiness/k8s/evidence-manifest.json
```

The manifest captures the real-cluster gate, required tools, generated rollout
steps, config hot-reload checklist, graceful shutdown checklist, report path,
archive path, and history path for the deployment evidence bundle.

## Current Boundaries

- Redis, PostgreSQL, Qdrant, and Ollama are expected to be provided separately.
- Ingress/Gateway resources and TLS certificate automation remain
  cluster-specific.
- NetworkPolicy is opt-in because not every target cluster has an enforcing
  controller; review egress rules for private model/search endpoints before
  enabling it.
- Real-cluster smoke tests remain explicitly gated operations work.
