# InsightDesk Helm MVP

This chart is a minimal Kubernetes deployment skeleton for InsightDesk. It is
intended to be small, reviewable, and statically verifiable before adding
cluster-specific production features.

## Included Resources

- API `Deployment` and `Service`.
- API probes on `/healthz` and `/readyz`.
- `ConfigMap` for core runtime settings.
- Optional ARQ worker `Deployment` with `worker.enabled=true`.
- Optional runtime `PersistentVolumeClaim` mounted at `/app/runtime`.
- Optional API `HorizontalPodAutoscaler` with `autoscaling.enabled=true`.
- Optional API `PodDisruptionBudget` with `podDisruptionBudget.enabled=true`.
- Optional `NetworkPolicy` resources for API, worker, Redis, Qdrant, and
  PostgreSQL with `networkPolicy.enabled=true`.
- Config changes trigger a rolling restart when
  `config.reloadStrategy=rolloutOnConfigChange`.

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
```

## NetworkPolicy

Network policies are disabled by default so the chart remains safe to render in
clusters without a NetworkPolicy controller. Enable them explicitly:

```bash
helm template insightdesk deploy/helm/insightdesk --set worker.enabled=true --set networkPolicy.enabled=true
```

The default policy set models these paths:

- API ingress on port `8000`.
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
- Sensitive settings are not yet modeled as Kubernetes `Secret` resources.
- Ingress, worker probes, and cluster smoke tests are still follow-up production
  hardening work.
