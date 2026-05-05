"""Verify persisted ops evidence for real-environment rollout drills.

Default mode is intentionally non-blocking so local validation can report the
current evidence state without requiring Docker, PostgreSQL, Qdrant, or K8s.
Use --strict during the deployment window to fail when any real drill evidence
is missing, skipped, failed, or not represented by its evidence manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy import run_ops_readiness as readiness

REAL_AREAS = {
    "1.2_async_queue": "arq",
    "1.3_storage_runtime": "storage",
    "4.3_deploy_ops": "k8s",
}


def _load_json(path: Path) -> tuple[dict[str, object] | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc.msg}"
    if not isinstance(loaded, dict):
        return None, "invalid_shape"
    return loaded, ""


def _manifest_entry(
    manifest: Mapping[str, object] | None,
    *,
    check_id: str,
    report_path: str,
) -> tuple[dict[str, object] | None, str]:
    if manifest is None:
        return None, "manifest_missing"

    reports = manifest.get("reports")
    if isinstance(reports, dict):
        report_stem = Path(report_path).stem
        entry = reports.get(check_id) or reports.get(report_stem)
        if isinstance(entry, dict):
            return entry, ""
        for value in reports.values():
            if not isinstance(value, dict):
                continue
            paths = value.get("paths")
            entry_report_path = (
                str(paths.get("report_path") or "") if isinstance(paths, dict) else ""
            )
            if entry_report_path and Path(entry_report_path) == Path(report_path):
                return value, ""
        return None, "manifest_entry_missing"

    # K8s rollout manifests are currently a single top-level artifact rather
    # than a reports map. Match by its persisted report path when available.
    paths = manifest.get("paths")
    manifest_report_path = (
        str(paths.get("report_path") or "") if isinstance(paths, dict) else ""
    )
    if manifest_report_path and Path(manifest_report_path) == Path(report_path):
        return dict(manifest), ""
    if str(manifest.get("id") or "") and not manifest_report_path:
        return dict(manifest), ""
    return None, "manifest_entry_missing"


def _report_closed(report: Mapping[str, object] | None) -> tuple[bool, list[str]]:
    if report is None:
        return False, ["report_missing"]

    blockers: list[str] = []
    if bool(report.get("skipped")):
        blockers.append("report_skipped")
    if report.get("ok") is not True:
        blockers.append("report_not_ok")

    status = str(report.get("status") or "")
    if status in {"failed", "blocked", "skipped", "error"}:
        blockers.append(f"report_status:{status}")

    report_blockers = report.get("blockers")
    if isinstance(report_blockers, list) and report_blockers:
        blockers.append("report_has_blockers")

    closure = report.get("closure")
    if isinstance(closure, dict):
        if closure.get("complete") is False:
            blockers.append("closure_incomplete")
        closure_blockers = closure.get("blockers")
        if isinstance(closure_blockers, list) and closure_blockers:
            blockers.append("closure_has_blockers")

    return not blockers, blockers


def _manifest_closed(
    entry: Mapping[str, object] | None,
    *,
    entry_problem: str,
) -> tuple[bool, list[str]]:
    if entry is None:
        return False, [entry_problem]

    blockers: list[str] = []
    if bool(entry.get("skipped")):
        blockers.append("manifest_skipped")
    if "ok" in entry and entry.get("ok") is not True:
        blockers.append("manifest_not_ok")

    status = str(entry.get("status") or "")
    if status in {"failed", "blocked", "skipped", "error"}:
        blockers.append(f"manifest_status:{status}")

    entry_blockers = entry.get("blockers")
    if isinstance(entry_blockers, list) and entry_blockers:
        blockers.append("manifest_has_blockers")

    return not blockers, blockers


def _read_area_manifests(
    checks: Sequence[readiness.OpsReadinessCheck],
) -> dict[str, dict[str, object]]:
    manifests: dict[str, dict[str, object]] = {}
    for check in checks:
        if not check.evidence_manifest_path:
            continue
        manifest_path = ROOT / check.evidence_manifest_path
        key = check.evidence_manifest_path
        if key in manifests:
            continue
        manifest, problem = _load_json(manifest_path)
        manifests[key] = {
            "path": check.evidence_manifest_path,
            "exists": manifest is not None,
            "problem": problem,
            "data": manifest,
        }
    return manifests


def build_evidence_verification_report(*, strict: bool = False) -> dict[str, object]:
    """Build a safe local report for all real-environment evidence artifacts."""

    real_checks = [check for check in readiness.all_readiness_checks() if check.real_environment]
    manifests = _read_area_manifests(real_checks)
    checks: list[dict[str, object]] = []

    for check in real_checks:
        report_data, report_problem = _load_json(ROOT / check.report_path)
        if report_problem:
            report_ok = False
            report_blockers: list[str] = []
        else:
            report_ok, report_blockers = _report_closed(report_data)

        manifest_state = manifests.get(check.evidence_manifest_path, {})
        manifest_data = manifest_state.get("data")
        entry, entry_problem = _manifest_entry(
            manifest_data if isinstance(manifest_data, dict) else None,
            check_id=check.id,
            report_path=check.report_path,
        )
        manifest_ok, manifest_blockers = _manifest_closed(
            entry,
            entry_problem=str(manifest_state.get("problem") or entry_problem),
        )

        blockers = []
        if report_problem:
            blockers.append(f"report:{report_problem}")
        blockers.extend(f"report:{item}" for item in report_blockers)
        blockers.extend(f"manifest:{item}" for item in manifest_blockers)

        closed = report_ok and manifest_ok and not blockers
        checks.append(
            {
                "id": check.id,
                "area": REAL_AREAS.get(check.area, check.area),
                "closed": closed,
                "report_path": check.report_path,
                "report_exists": report_data is not None,
                "manifest_path": check.evidence_manifest_path,
                "manifest_exists": bool(manifest_state.get("exists")),
                "manifest_entry_exists": entry is not None,
                "status": "closed" if closed else "pending",
                "blockers": blockers,
            }
        )

    closed = [item for item in checks if bool(item["closed"])]
    pending = [item for item in checks if not bool(item["closed"])]
    area_summary: dict[str, dict[str, int]] = {}
    for item in checks:
        area = str(item["area"])
        area_summary.setdefault(area, {"total": 0, "closed": 0, "pending": 0})
        area_summary[area]["total"] += 1
        if bool(item["closed"]):
            area_summary[area]["closed"] += 1
        else:
            area_summary[area]["pending"] += 1

    all_closed = not pending
    return {
        "ok": all_closed if strict else True,
        "strict": strict,
        "all_closed": all_closed,
        "summary": {
            "total": len(checks),
            "closed": len(closed),
            "pending": len(pending),
            "areas": area_summary,
        },
        "checks": checks,
        "blockers": [
            f"{item['id']}:{','.join(str(blocker) for blocker in item['blockers'])}"
            for item in pending
            if item.get("blockers")
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify persisted ops evidence artifacts.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless every real-environment drill is closed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_evidence_verification_report(strict=args.strict)
    if args.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    else:
        summary = report["summary"]
        print(
            "summary: "
            f"closed={summary['closed']} "
            f"pending={summary['pending']} "
            f"strict={str(report['strict']).lower()}"
        )
        for item in report["checks"]:
            print(f"- {item['status']} {item['id']}: {item['report_path']}")
            blockers = item.get("blockers") or []
            if blockers:
                print(f"  blockers: {', '.join(blockers)}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
