from deploy.validate_helm_static import validate_chart


def test_helm_mvp_static_contract() -> None:
    assert validate_chart() == []


def test_helm_network_policy_values_cover_core_paths() -> None:
    values = (
        validate_chart.__globals__["CHART_DIR"] / "values.yaml"
    ).read_text(encoding="utf-8")

    required_snippets = [
        "networkPolicy:",
        "enabled: false",
        "api:",
        "worker:",
        "dependencies:",
        "redis:",
        "qdrant:",
        "postgres:",
        "port: 6379",
        "port: 6333",
        "port: 5432",
        "app.kubernetes.io/component: api",
        "app.kubernetes.io/component: worker",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in values]
    assert missing == []


def test_helm_network_policy_template_is_optional_and_templatable() -> None:
    chart_dir = validate_chart.__globals__["CHART_DIR"]
    template = (chart_dir / "templates" / "networkpolicy.yaml").read_text(
        encoding="utf-8"
    )

    required_snippets = [
        "{{- if .Values.networkPolicy.enabled }}",
        "kind: NetworkPolicy",
        "{{- if .Values.networkPolicy.api.enabled }}",
        "{{- if and .Values.worker.enabled .Values.networkPolicy.worker.enabled }}",
        "{{- range $name, $policy := .Values.networkPolicy.dependencies }}",
        "{{- toYaml .Values.networkPolicy.api.ingress",
        "{{- toYaml .Values.networkPolicy.api.egress",
        "{{- toYaml .Values.networkPolicy.worker.ingress",
        "{{- toYaml .Values.networkPolicy.worker.egress",
        "{{- toYaml $policy.podSelector",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in template]
    assert missing == []


def test_helm_config_reload_and_shutdown_contract() -> None:
    chart_dir = validate_chart.__globals__["CHART_DIR"]
    api = (chart_dir / "templates" / "deployment-api.yaml").read_text(
        encoding="utf-8"
    )
    worker = (chart_dir / "templates" / "deployment-worker.yaml").read_text(
        encoding="utf-8"
    )
    values = (chart_dir / "values.yaml").read_text(encoding="utf-8")

    for content in (api, worker):
        assert "checksum/config:" in content
        assert "rolloutOnConfigChange" in content
        assert "config.insightdesk/reload-strategy:" in content
        assert ".Values.config.hotReload.enabled" in content
        assert "runtime-config" in content
        assert "terminationGracePeriodSeconds:" in content
        assert "preStop:" in values
        assert "sleep 5" in values


def test_helm_config_hot_reload_contract_is_static_and_optional() -> None:
    chart_dir = validate_chart.__globals__["CHART_DIR"]
    values = (chart_dir / "values.yaml").read_text(encoding="utf-8")
    configmap = (chart_dir / "templates" / "configmap.yaml").read_text(
        encoding="utf-8"
    )

    required_values = [
        "reloadStrategy: rolloutOnConfigChange",
        "hotReload:",
        "enabled: false",
        "mountPath: /app/runtime/config",
        "fileName: insightdesk.env",
        "checkIntervalSeconds:",
    ]
    assert [snippet for snippet in required_values if snippet not in values] == []

    required_configmap = [
        "CONFIG_RELOAD_STRATEGY:",
        "CONFIG_HOT_RELOAD_ENABLED:",
        "CONFIG_HOT_RELOAD_PATH:",
        "CONFIG_HOT_RELOAD_CHECK_INTERVAL_SECONDS:",
        "{{ .Values.config.hotReload.fileName }}: |-",
    ]
    assert [snippet for snippet in required_configmap if snippet not in configmap] == []


def test_k8s_rollout_drill_exposes_config_reload_contract() -> None:
    from deploy import run_k8s_rollout_drill as drill

    report = drill.build_k8s_rollout_drill_report(
        env={"OPS_REAL_CLUSTER_TEST": "0"},
        report_path="runtime/ops-readiness/k8s/test.json",
        archive_dir="runtime/ops-readiness/k8s/archive",
        history_path="runtime/ops-readiness/k8s/history.json",
    )

    contract = report["contracts"]["config_reload"]
    assert contract["strategy_default"] == "rolloutOnConfigChange"
    assert contract["checksum_rollout_annotation"] is True
    assert contract["mounted_config_supported"] is True
    assert contract["hot_reload_checklist"]
    assert contract["expected_refresh_mechanism"] in {
        "checksum_rollout",
        "mounted_config_hot_reload",
    }
    assert report["summary"]["config_reload_ready"] is True

    shutdown_contract = report["contracts"]["graceful_shutdown"]
    assert shutdown_contract["ready"] is True
    assert shutdown_contract["graceful_shutdown_checklist"]
    assert report["summary"]["graceful_shutdown_ready"] is True


def test_helm_static_validation_covers_real_cluster_drill_runner() -> None:
    runner = validate_chart.__globals__["K8S_ROLLOUT_DRILL_RUNNER"].read_text(
        encoding="utf-8"
    )

    required = [
        "OPS_REAL_CLUSTER_TEST",
        "helm template",
        "rollout",
        "status",
        "build_graceful_shutdown_contract",
        "build_evidence_manifest",
        "report_path",
        "manifest_path",
        "json.dumps",
    ]
    assert [snippet for snippet in required if snippet not in runner] == []
