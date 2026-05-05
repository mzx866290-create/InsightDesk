"""Env-gated PostgreSQL/Qdrant integration contract check.

The script is intentionally inert by default. It only opens real PostgreSQL or
Qdrant connections when STORAGE_INTEGRATION_TEST=1 and the matching target
environment variables are present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.storage_runtime import (
    STORAGE_MIGRATION_EXECUTE_ENV,
    STORAGE_MIGRATION_ROLLBACK_ENV,
    SUPPORTED_QDRANT_URL_SCHEMES,
    storage_readiness_contract,
    storage_rollback_contract,
    validate_postgres_config,
    validate_qdrant_config,
)
from deploy.validate_storage_migration import POSTGRES_ADAPTER_TABLES


INTEGRATION_GATE_ENV = "STORAGE_INTEGRATION_TEST"
QDRANT_TEST_COLLECTION_PREFIX = "insightdesk_test_"
DEFAULT_EVIDENCE_ID = "storage_real_integration"


PostgresChecker = Callable[[str], dict[str, Any]]
QdrantChecker = Callable[[str, str, str, str], dict[str, Any]]


def _env_value(env: Mapping[str, str], key: str) -> str:
    return str(env.get(key) or "").strip()


def _redact_url(raw_url: str) -> str:
    normalized = str(raw_url or "").strip()
    if not normalized:
        return ""
    parsed = urlsplit(normalized)
    if not parsed.scheme or not parsed.netloc:
        return "<configured>"

    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    userinfo = "***:***@" if parsed.username or parsed.password else ""
    return urlunsplit((parsed.scheme, f"{userinfo}{host}{port}", parsed.path, "", ""))


def _qdrant_test_collection(env: Mapping[str, str]) -> str:
    configured = _env_value(env, "QDRANT_TEST_COLLECTION")
    if configured:
        return configured
    return f"{QDRANT_TEST_COLLECTION_PREFIX}{uuid4().hex}"


def _skip_entry(name: str, reason: str) -> dict[str, str]:
    return {"name": name, "reason": reason}


def _check_entry(name: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "status": status, "details": details or {}}


def _integration_status(payload: dict[str, Any]) -> str:
    if not payload["integration_enabled"]:
        return "skipped"
    if payload["errors"]:
        return "blocked"
    return "passed"


def _finalize_integration_payload(payload: dict[str, Any]) -> None:
    status = _integration_status(payload)
    payload["status"] = status
    payload["ok"] = status in {"passed", "skipped"}
    payload["gate"]["status"] = "passed" if payload["integration_enabled"] else "skipped"
    payload["pre_checks"] = [
        _check_entry(
            "storage_integration_env_gate",
            payload["gate"]["status"],
            {
                "env": INTEGRATION_GATE_ENV,
                "required_value": "1",
                "configured": payload["integration_enabled"],
            },
        ),
        _check_entry(
            "postgres_config",
            "passed"
            if payload["postgres"].get("dsn_configured") and not payload["postgres"].get("warnings")
            else "blocked"
            if payload["integration_enabled"]
            else "skipped",
            {
                "dsn_configured": payload["postgres"].get("dsn_configured"),
                "warnings": payload["postgres"].get("warnings", []),
            },
        ),
        _check_entry(
            "qdrant_config",
            "passed"
            if payload["qdrant"].get("url_configured") and not payload["qdrant"].get("warnings")
            else "blocked"
            if payload["integration_enabled"]
            else "skipped",
            {
                "url_configured": payload["qdrant"].get("url_configured"),
                "warnings": payload["qdrant"].get("warnings", []),
            },
        ),
        _check_entry(
            "qdrant_test_collection_safety",
            "skipped"
            if not payload["integration_enabled"]
            else "passed"
            if str(payload["qdrant"].get("test_collection") or "").startswith(
                QDRANT_TEST_COLLECTION_PREFIX
            )
            else "blocked",
            {
                "safe_prefix": QDRANT_TEST_COLLECTION_PREFIX,
                "test_collection": payload["qdrant"].get("test_collection"),
            },
        ),
    ]
    payload["post_checks"] = [
        _check_entry(
            "postgres_real_check",
            "passed"
            if payload["postgres"].get("checked") and not payload["postgres"].get("errors")
            else "skipped"
            if not payload["integration_enabled"] or payload["postgres"].get("skipped")
            else "blocked",
            {
                "checked": payload["postgres"].get("checked"),
                "schema_ready": payload["postgres"].get("schema", {}).get("ready"),
            },
        ),
        _check_entry(
            "qdrant_real_check",
            "passed"
            if payload["qdrant"].get("checked") and not payload["qdrant"].get("errors")
            else "skipped"
            if not payload["integration_enabled"] or payload["qdrant"].get("skipped")
            else "blocked",
            {
                "checked": payload["qdrant"].get("checked"),
                "roundtrip": payload["qdrant"].get("roundtrip", {}),
            },
        ),
        _check_entry("evidence_persistence", "pending"),
    ]
    payload["evidence_bundle"] = {
        "id": DEFAULT_EVIDENCE_ID,
        "status": status,
        "integration_enabled": payload["integration_enabled"],
        "gate": payload["gate"],
        "checked": payload["checked"],
        "skipped": payload["skipped"],
        "checks": {
            "pre": payload["pre_checks"],
            "post": payload["post_checks"],
        },
        "targets": {
            "report_path": "",
            "archive_dir": "",
            "history_path": "",
            "manifest_path": "",
        },
        "artifacts": {
            "report": {"path": "", "written": False},
            "archive": {"dir": "", "path": "", "written": False},
            "history": {"path": "", "written": False},
            "manifest": {"path": "", "written": False},
        },
    }


def _empty_postgres_payload(dsn: str) -> dict[str, Any]:
    config = validate_postgres_config(dsn)
    return {
        "checked": False,
        "skipped": True,
        "dsn": config["target"]["dsn_preview"],
        "dsn_configured": bool(dsn),
        "schema": {
            "required_tables": list(POSTGRES_ADAPTER_TABLES),
            "present_tables": [],
            "missing_tables": [],
            "ready": False,
        },
        "warnings": list(config["warnings"]),
        "errors": [],
    }


def _empty_qdrant_payload(
    *,
    url: str,
    collection: str,
    test_collection: str,
    api_key: str,
) -> dict[str, Any]:
    config = validate_qdrant_config(
        url=url,
        collection_name=collection or test_collection,
        api_key=api_key,
    )
    return {
        "checked": False,
        "skipped": True,
        "url": _redact_url(url),
        "url_configured": bool(url),
        "collection": collection,
        "test_collection": test_collection,
        "api_key_configured": bool(api_key),
        "collections_endpoint": {
            "checked": False,
            "available": False,
            "collection_count": None,
        },
        "warnings": list(config["warnings"]),
        "errors": [],
    }


def check_postgres(dsn: str) -> dict[str, Any]:
    """Open PostgreSQL and verify required adapter tables are visible."""

    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is required for PostgreSQL integration checks.") from exc

    present_tables: list[str] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
            for table_name in POSTGRES_ADAPTER_TABLES:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = current_schema()
                          AND table_name = %s
                    )
                    """,
                    (table_name,),
                )
                exists = bool(cursor.fetchone()[0])
                if exists:
                    present_tables.append(table_name)

    missing_tables = [
        table_name
        for table_name in POSTGRES_ADAPTER_TABLES
        if table_name not in present_tables
    ]
    return {
        "connectivity": {"checked": True, "available": True},
        "schema": {
            "required_tables": list(POSTGRES_ADAPTER_TABLES),
            "present_tables": present_tables,
            "missing_tables": missing_tables,
            "ready": not missing_tables,
        },
        "warnings": [],
        "errors": [] if not missing_tables else ["postgres_adapter_tables_missing"],
    }


def check_qdrant(
    url: str,
    api_key: str,
    collection: str,
    test_collection: str,
) -> dict[str, Any]:
    """Open Qdrant, verify collections endpoint, and run a safe test collection roundtrip."""

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams
    except ModuleNotFoundError as exc:
        raise RuntimeError("qdrant-client is required for Qdrant integration checks.") from exc

    client = QdrantClient(url=url, api_key=api_key or None)
    collections = client.get_collections()
    collection_names = [
        str(item.name)
        for item in getattr(collections, "collections", [])
        if getattr(item, "name", None)
    ]
    if test_collection in collection_names:
        return {
            "collections_endpoint": {
                "checked": True,
                "available": True,
                "collection_count": len(collection_names),
            },
            "roundtrip": {"checked": False, "created": False, "deleted": False},
            "warnings": [],
            "errors": ["qdrant_test_collection_already_exists"],
        }

    created = False
    deleted = False
    try:
        client.create_collection(
            collection_name=test_collection,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE),
        )
        created = True
        client.upsert(
            collection_name=test_collection,
            points=[
                PointStruct(
                    id=1,
                    vector=[0.1, 0.2, 0.3, 0.4],
                    payload={"source": "storage-integration-contract"},
                )
            ],
        )
        count = client.count(collection_name=test_collection, exact=True)
        roundtrip_count = int(getattr(count, "count", 0) or 0)
    finally:
        if created and test_collection.startswith(QDRANT_TEST_COLLECTION_PREFIX):
            delete_result = client.delete_collection(collection_name=test_collection)
            deleted = delete_result is not False

    return {
        "collections_endpoint": {
            "checked": True,
            "available": True,
            "collection_count": len(collection_names),
        },
        "roundtrip": {
            "checked": True,
            "created": created,
            "deleted": deleted,
            "point_count": roundtrip_count,
        },
        "target_collection_seen": collection in collection_names if collection else None,
        "warnings": [],
        "errors": [] if roundtrip_count == 1 and deleted else ["qdrant_roundtrip_failed"],
    }


def build_integration_report(
    env: Mapping[str, str] | None = None,
    *,
    postgres_checker: PostgresChecker = check_postgres,
    qdrant_checker: QdrantChecker = check_qdrant,
) -> dict[str, Any]:
    """Build the JSON payload for the env-gated real storage integration check."""

    current_env = os.environ if env is None else env
    enabled = _env_value(current_env, INTEGRATION_GATE_ENV) == "1"
    postgres_dsn = _env_value(current_env, "DATABASE_URL") or _env_value(
        current_env,
        "POSTGRES_DSN",
    )
    qdrant_url = _env_value(current_env, "QDRANT_URL")
    qdrant_collection = _env_value(current_env, "QDRANT_COLLECTION")
    qdrant_api_key = _env_value(current_env, "QDRANT_API_KEY")
    qdrant_test_collection = _qdrant_test_collection(current_env)

    payload: dict[str, Any] = {
        "ok": True,
        "status": "pending",
        "integration_enabled": enabled,
        "gate": {
            "env": INTEGRATION_GATE_ENV,
            "required_value": "1",
            "configured": enabled,
            "status": "pending",
        },
        "checked": [],
        "skipped": [],
        "errors": [],
        "warnings": [],
        "postgres": _empty_postgres_payload(postgres_dsn),
        "qdrant": _empty_qdrant_payload(
            url=qdrant_url,
            collection=qdrant_collection,
            test_collection=qdrant_test_collection,
            api_key=qdrant_api_key,
        ),
        "contracts": {
            "readiness": storage_readiness_contract(),
            "rollback": storage_rollback_contract(),
            "execute_command": [
                "python",
                "deploy/validate_storage_migration.py",
                "--execute",
                "--json",
            ],
            "execute_env": STORAGE_MIGRATION_EXECUTE_ENV,
            "rollback_command": [
                "python",
                "deploy/validate_storage_migration.py",
                "--rollback",
                "--json",
            ],
            "rollback_env": STORAGE_MIGRATION_ROLLBACK_ENV,
        },
    }

    if not enabled:
        payload["skipped"].append(_skip_entry("postgres", "integration_disabled"))
        payload["skipped"].append(_skip_entry("qdrant", "integration_disabled"))
        _finalize_integration_payload(payload)
        return payload

    postgres_config = validate_postgres_config(postgres_dsn)
    if not postgres_config["valid"]:
        payload["errors"].extend(f"postgres:{warning}" for warning in postgres_config["warnings"])
        payload["skipped"].append(_skip_entry("postgres", "invalid_config"))
    else:
        try:
            postgres_result = postgres_checker(postgres_dsn)
            payload["postgres"].update(postgres_result)
            payload["postgres"]["checked"] = True
            payload["postgres"]["skipped"] = False
            payload["checked"].append("postgres")
            payload["warnings"].extend(
                f"postgres:{warning}" for warning in postgres_result.get("warnings", [])
            )
            payload["errors"].extend(
                f"postgres:{error}" for error in postgres_result.get("errors", [])
            )
        except Exception as exc:  # pragma: no cover - exercised by deployment failures.
            payload["errors"].append(f"postgres:connection_failed:{type(exc).__name__}")

    parsed_qdrant_scheme = urlsplit(qdrant_url).scheme.lower()
    qdrant_config = validate_qdrant_config(
        url=qdrant_url,
        collection_name=qdrant_collection or qdrant_test_collection,
        api_key=qdrant_api_key,
    )
    if not qdrant_url:
        payload["errors"].append("qdrant:qdrant_url_missing")
        payload["skipped"].append(_skip_entry("qdrant", "missing_url"))
    elif parsed_qdrant_scheme not in SUPPORTED_QDRANT_URL_SCHEMES:
        payload["errors"].append("qdrant:qdrant_url_invalid_scheme")
        payload["skipped"].append(_skip_entry("qdrant", "invalid_config"))
    elif not qdrant_test_collection.startswith(QDRANT_TEST_COLLECTION_PREFIX):
        payload["errors"].append("qdrant:test_collection_prefix_required")
        payload["skipped"].append(_skip_entry("qdrant", "unsafe_test_collection"))
    elif not qdrant_config["valid"]:
        payload["errors"].extend(f"qdrant:{warning}" for warning in qdrant_config["warnings"])
        payload["skipped"].append(_skip_entry("qdrant", "invalid_config"))
    else:
        try:
            qdrant_result = qdrant_checker(
                qdrant_url,
                qdrant_api_key,
                qdrant_collection,
                qdrant_test_collection,
            )
            payload["qdrant"].update(qdrant_result)
            payload["qdrant"]["checked"] = True
            payload["qdrant"]["skipped"] = False
            payload["checked"].append("qdrant")
            payload["warnings"].extend(
                f"qdrant:{warning}" for warning in qdrant_result.get("warnings", [])
            )
            payload["errors"].extend(
                f"qdrant:{error}" for error in qdrant_result.get("errors", [])
            )
        except Exception as exc:  # pragma: no cover - exercised by deployment failures.
            payload["errors"].append(f"qdrant:connection_failed:{type(exc).__name__}")

    _finalize_integration_payload(payload)
    return payload


def emit_evidence_report(
    report: dict[str, Any],
    *,
    report_path: str = "",
    archive_dir: str = "",
    history_path: str = "",
    manifest_path: str = "",
    evidence_id: str = DEFAULT_EVIDENCE_ID,
) -> None:
    """Write local JSON evidence files without changing integration behavior."""

    if not (report_path or archive_dir or history_path or manifest_path):
        return

    bundle = report.setdefault(
        "evidence_bundle",
        {
            "id": evidence_id,
            "status": report.get("status", "unknown"),
            "checks": {
                "pre": report.get("pre_checks", []),
                "post": report.get("post_checks", []),
            },
            "artifacts": {},
        },
    )
    bundle["id"] = evidence_id
    bundle["status"] = report.get("status", bundle.get("status"))
    bundle["targets"] = {
        "report_path": report_path,
        "archive_dir": archive_dir,
        "history_path": history_path,
        "manifest_path": manifest_path,
    }
    artifacts = bundle.setdefault("artifacts", {})
    artifacts["report"] = {"path": report_path, "written": bool(report_path)}
    artifacts["archive"] = {"dir": archive_dir, "path": "", "written": bool(archive_dir)}
    artifacts["history"] = {"path": history_path, "written": bool(history_path)}
    artifacts["manifest"] = {"path": manifest_path, "written": bool(manifest_path)}
    for check in bundle.get("checks", {}).get("post", []):
        if check.get("name") == "evidence_persistence":
            check["status"] = "passed"
            check["details"] = {
                "report_path": report_path,
                "archive_dir": archive_dir,
                "history_path": history_path,
                "manifest_path": manifest_path,
            }
    report["evidence"] = {
        "id": evidence_id,
        "bundle_id": evidence_id,
        "status": report.get("status", "unknown"),
        "report_path": report_path,
        "archive_dir": archive_dir,
        "history_path": history_path,
        "manifest_path": manifest_path,
        "archive_path": "",
    }
    if archive_dir:
        archive_root = Path(archive_dir)
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{evidence_id}-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}.json"
        archive_path = archive_root / archive_name
        report["evidence"]["archive_path"] = str(archive_path)
        artifacts["archive"]["path"] = str(archive_path)
        archive_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if history_path:
        history = Path(history_path)
        history.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict[str, Any]] = []
        if history.is_file():
            try:
                loaded = json.loads(history.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    entries = loaded
            except json.JSONDecodeError:
                entries = []
        entries.append(
            {
                "id": evidence_id,
                "ok": report["ok"],
                "status": report.get("status"),
                "integration_enabled": report["integration_enabled"],
                "checked": report["checked"],
                "skipped": report["skipped"],
                "errors": report["errors"],
                "evidence_bundle_id": evidence_id,
                "report_path": report_path,
                "archive_path": report["evidence"]["archive_path"],
                "history_path": history_path,
                "manifest_path": manifest_path,
                "recorded_at": time.time(),
            }
        )
        history.write_text(
            json.dumps(entries[-100:], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if manifest_path:
        _write_evidence_manifest(
            report,
            evidence_id=evidence_id,
            manifest_path=manifest_path,
            report_path=report_path,
            history_path=history_path,
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_evidence_manifest(
    report: dict[str, Any],
    *,
    evidence_id: str,
    manifest_path: str,
    report_path: str,
    history_path: str,
) -> None:
    """Update the evidence manifest while preserving other check entries."""

    manifest_file = Path(manifest_path)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {}
    if manifest_file.is_file():
        try:
            loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
        except json.JSONDecodeError:
            manifest = {}

    finished_at = _utc_now_iso()
    manifest["schema_version"] = str(manifest.get("schema_version") or "1")
    manifest["updated_at"] = finished_at
    reports = manifest.setdefault("reports", {})
    if not isinstance(reports, dict):
        reports = {}
        manifest["reports"] = reports
    reports[evidence_id] = {
        "id": evidence_id,
        "status": report.get("status"),
        "gate": report.get("gate", {}),
        "ok": report.get("ok"),
        "report_path": report_path,
        "archive_path": report.get("evidence", {}).get("archive_path", ""),
        "history_path": history_path,
        "manifest_path": manifest_path,
        "blockers": list(report.get("errors", [])),
        "finished_at": finished_at,
    }
    report["evidence_bundle"]["artifacts"]["manifest"]["written"] = True
    manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run env-gated real PostgreSQL/Qdrant storage integration checks."
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of pretty JSON.",
    )
    parser.add_argument("--report-path", default="")
    parser.add_argument("--archive-dir", default="")
    parser.add_argument("--history-path", default="")
    parser.add_argument("--manifest-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_integration_report()
    emit_evidence_report(
        report,
        report_path=args.report_path,
        archive_dir=args.archive_dir,
        history_path=args.history_path,
        manifest_path=args.manifest_path,
    )
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":") if args.compact else None,
            indent=None if args.compact else 2,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
