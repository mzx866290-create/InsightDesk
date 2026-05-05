"""Static checks for the InsightDesk Helm MVP chart.

The script intentionally avoids requiring a Kubernetes cluster or the Helm
binary, so it can run in lightweight CI and on developer machines.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = ROOT / "deploy" / "helm" / "insightdesk"
K8S_ROLLOUT_DRILL_RUNNER = ROOT / "deploy" / "run_k8s_rollout_drill.py"

REQUIRED_FILES = [
    "Chart.yaml",
    "values.yaml",
    "templates/_helpers.tpl",
    "templates/configmap.yaml",
    "templates/deployment-api.yaml",
    "templates/deployment-worker.yaml",
    "templates/networkpolicy.yaml",
    "templates/service.yaml",
    "templates/pvc.yaml",
    "templates/hpa.yaml",
    "templates/pdb.yaml",
    "README.md",
]

REQUIRED_SNIPPETS = {
    "Chart.yaml": ["apiVersion: v2", "name: insightdesk", "type: application"],
    "values.yaml": [
        "image:",
        "runtime:",
        "worker:",
        "autoscaling:",
        "livenessProbe:",
        "readinessProbe:",
        "path: /healthz",
        "path: /readyz",
        "terminationGracePeriodSeconds:",
        "preStop:",
        "podDisruptionBudget:",
        "arq backend.tasks.worker.WorkerSettings",
        "reloadStrategy: rolloutOnConfigChange",
        "hotReload:",
        "mountPath: /app/runtime/config",
        "fileName: insightdesk.env",
        "networkPolicy:",
        "enabled: false",
        "dependencies:",
        "redis:",
        "qdrant:",
        "postgres:",
    ],
    "templates/configmap.yaml": [
        "CONFIG_RELOAD_STRATEGY:",
        "CONFIG_HOT_RELOAD_ENABLED:",
        "CONFIG_HOT_RELOAD_PATH:",
        "CONFIG_HOT_RELOAD_CHECK_INTERVAL_SECONDS:",
        ".Values.config.hotReload.fileName",
    ],
    "templates/deployment-api.yaml": [
        "kind: Deployment",
        "app.kubernetes.io/component: api",
        "checksum/config:",
        "rolloutOnConfigChange",
        "config.insightdesk/reload-strategy:",
        "runtime-config",
        ".Values.config.hotReload.enabled",
        "livenessProbe:",
        "readinessProbe:",
        "terminationGracePeriodSeconds:",
        "lifecycle:",
        "mountPath: /app/runtime",
    ],
    "templates/deployment-worker.yaml": [
        "{{- if .Values.worker.enabled }}",
        "app.kubernetes.io/component: worker",
        "checksum/config:",
        "rolloutOnConfigChange",
        "config.insightdesk/reload-strategy:",
        "runtime-config",
        ".Values.config.hotReload.enabled",
        "terminationGracePeriodSeconds:",
        "lifecycle:",
        "value: arq",
    ],
    "templates/networkpolicy.yaml": [
        "networking.k8s.io/v1",
        "kind: NetworkPolicy",
        ".Values.networkPolicy.enabled",
        ".Values.networkPolicy.api.enabled",
        ".Values.networkPolicy.worker.enabled",
        ".Values.networkPolicy.dependencies",
        "app.kubernetes.io/component: api",
        "app.kubernetes.io/component: worker",
        "app.kubernetes.io/component: {{ $name }}",
        "policyTypes:",
        "Ingress",
        "Egress",
    ],
    "templates/service.yaml": ["kind: Service", "targetPort: http"],
    "templates/pvc.yaml": ["kind: PersistentVolumeClaim", "storage:"],
    "templates/hpa.yaml": ["kind: HorizontalPodAutoscaler", "autoscaling/v2"],
    "templates/pdb.yaml": [
        "{{- if .Values.podDisruptionBudget.enabled }}",
        "kind: PodDisruptionBudget",
        "policy/v1",
        "minAvailable:",
        "app.kubernetes.io/component: api",
    ],
    "README.md": [
        "helm lint deploy/helm/insightdesk",
        "helm template insightdesk deploy/helm/insightdesk",
        "--set networkPolicy.enabled=true",
        "rolloutOnConfigChange",
        "NetworkPolicy",
        "Real-Cluster Evidence",
        "--manifest-path",
        "hot_reload_checklist",
        "graceful_shutdown_checklist",
    ],
}

REQUIRED_RUNNER_SNIPPETS = [
    "OPS_REAL_CLUSTER_TEST",
    "helm template",
    "kubectl",
    "rollout",
    "status",
    "build_config_reload_contract",
    "build_graceful_shutdown_contract",
    "build_real_cluster_contract",
    "build_evidence_manifest",
    "config_reload_ready",
    "graceful_shutdown_ready",
    "hot_reload_checklist",
    "graceful_shutdown_checklist",
    "real_cluster",
    "manifest_path",
    "report_path",
    "json.dumps",
]

REQUIRED_OCCURRENCES = {
    "templates/deployment-api.yaml": {
        "terminationGracePeriodSeconds:": 1,
        "lifecycle:": 1,
    },
    "templates/deployment-worker.yaml": {
        "terminationGracePeriodSeconds:": 1,
        "lifecycle:": 1,
    },
}


def validate_chart() -> list[str]:
    errors: list[str] = []
    if not CHART_DIR.exists():
        return [f"missing chart directory: {CHART_DIR}"]

    for relative_path in REQUIRED_FILES:
        path = CHART_DIR / relative_path
        if not path.is_file():
            errors.append(f"missing required file: {relative_path}")

    for relative_path, snippets in REQUIRED_SNIPPETS.items():
        path = CHART_DIR / relative_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in content:
                errors.append(f"{relative_path} missing snippet: {snippet}")
        for snippet, minimum_count in REQUIRED_OCCURRENCES.get(relative_path, {}).items():
            actual_count = content.count(snippet)
            if actual_count < minimum_count:
                errors.append(
                    f"{relative_path} expected at least {minimum_count} occurrence(s) of {snippet}, "
                    f"found {actual_count}"
                )

    if not K8S_ROLLOUT_DRILL_RUNNER.is_file():
        errors.append(f"missing K8s rollout drill runner: {K8S_ROLLOUT_DRILL_RUNNER}")
    else:
        runner = K8S_ROLLOUT_DRILL_RUNNER.read_text(encoding="utf-8")
        for snippet in REQUIRED_RUNNER_SNIPPETS:
            if snippet not in runner:
                errors.append(f"run_k8s_rollout_drill.py missing snippet: {snippet}")

    return errors


def main() -> int:
    errors = validate_chart()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: Helm static checks passed for {CHART_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
