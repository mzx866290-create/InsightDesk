"""Static checks for the InsightDesk Prometheus alert rule templates.

The validator intentionally avoids requiring promtool or PyYAML so it can run
in the same lightweight CI path as the existing Helm static checks.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALERT_RULES_FILE = ROOT / "deploy" / "alerts" / "insightdesk-arq-alerts.yml"

REQUIRED_ALERTS = [
    "InsightDeskArqQueueBacklog",
    "InsightDeskArqWorkerHeartbeatMissing",
    "InsightDeskTaskPendingStale",
    "InsightDeskTaskRunningStale",
    "InsightDeskTaskQueueHealthUnavailable",
    "InsightDeskOperationsAlertsPresent",
]

REQUIRED_SNIPPETS = [
    "groups:",
    "name: insightdesk-arq",
    "rules:",
    "expr:",
    "for:",
    "severity:",
    "annotations:",
    "insightdesk_operations_alerts",
    "insightdesk_task_queue_health",
    'code="arq_queue_backlog"',
    'code="arq_worker_heartbeat_missing"',
    'code="task_pending_stale"',
    'code="task_running_stale"',
    'code="arq_queue_health_unavailable"',
]


def validate_alert_rules() -> list[str]:
    errors: list[str] = []
    if not ALERT_RULES_FILE.is_file():
        return [f"missing alert rules file: {ALERT_RULES_FILE}"]

    content = ALERT_RULES_FILE.read_text(encoding="utf-8")
    for alert_name in REQUIRED_ALERTS:
        if f"alert: {alert_name}" not in content:
            errors.append(f"missing alert rule: {alert_name}")

    for snippet in REQUIRED_SNIPPETS:
        if snippet not in content:
            errors.append(f"missing alert rules snippet: {snippet}")

    if content.count("alert: ") != len(REQUIRED_ALERTS):
        errors.append(
            f"expected {len(REQUIRED_ALERTS)} alert rules, found {content.count('alert: ')}"
        )

    return errors


def main() -> int:
    errors = validate_alert_rules()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: alert rule static checks passed for {ALERT_RULES_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
