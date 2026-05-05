from __future__ import annotations

from pathlib import Path

from deploy.validate_alert_rules_static import validate_alert_rules


ROOT = Path(__file__).resolve().parents[1]
ALERT_RULES_FILE = ROOT / "deploy" / "alerts" / "insightdesk-arq-alerts.yml"


def test_arq_alert_rules_static_contract() -> None:
    assert validate_alert_rules() == []


def test_arq_alert_rules_template_contains_required_alerts_and_metrics() -> None:
    content = ALERT_RULES_FILE.read_text(encoding="utf-8")

    # Keep this check dependency-free: the production validator owns YAML details.
    required_snippets = [
        "InsightDeskArqQueueBacklog",
        "InsightDeskArqWorkerHeartbeatMissing",
        "InsightDeskTaskPendingStale",
        "InsightDeskTaskRunningStale",
        "InsightDeskTaskQueueHealthUnavailable",
        "insightdesk_operations_alerts",
        "insightdesk_task_queue_health",
        "arq_queue_backlog",
        "arq_worker_heartbeat_missing",
        "task_pending_stale",
        "task_running_stale",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []
