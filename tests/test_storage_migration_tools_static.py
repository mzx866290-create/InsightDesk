from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_FILE = ROOT / "deploy" / "validate_storage_migration.py"
INTEGRATION_CHECK_FILE = ROOT / "deploy" / "run_storage_integration_check.py"
QDRANT_BACKFILL_FILE = ROOT / "deploy" / "run_qdrant_backfill.py"


def _read_validator() -> str:
    assert VALIDATOR_FILE.exists(), "deploy/validate_storage_migration.py must exist"
    return VALIDATOR_FILE.read_text(encoding="utf-8")


def _read_integration_check() -> str:
    assert INTEGRATION_CHECK_FILE.exists(), "deploy/run_storage_integration_check.py must exist"
    return INTEGRATION_CHECK_FILE.read_text(encoding="utf-8")


def _read_qdrant_backfill() -> str:
    assert QDRANT_BACKFILL_FILE.exists(), "deploy/run_qdrant_backfill.py must exist"
    return QDRANT_BACKFILL_FILE.read_text(encoding="utf-8")


def test_storage_migration_validator_locks_runtime_config_contract() -> None:
    content = _read_validator()

    required_snippets = [
        "storage_runtime_payload",
        "DATABASE_PROVIDER",
        "APP_DB_PATH",
        "DATABASE_URL",
        "POSTGRES_DSN",
        "VECTOR_STORE_PROVIDER",
        "QDRANT_URL",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_storage_migration_validator_locks_low_risk_postgres_tables() -> None:
    content = _read_validator()

    required_snippets = [
        '"sessions"',
        '"workspaces"',
        '"bookmarks"',
        '"system_prompts"',
        '"organizations"',
        '"users"',
        '"memberships"',
        '"share_links"',
        '"sso_sessions"',
        'CREATE TABLE IF NOT EXISTS organizations',
        'CREATE TABLE IF NOT EXISTS share_links',
        'CREATE TABLE IF NOT EXISTS sso_sessions',
        '"postgres_adapter_coverage_ratio"',
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_storage_migration_validator_locks_json_cli_contract() -> None:
    content = _read_validator()

    required_snippets = [
        "json.dumps",
        "ensure_ascii=False",
        "print(",
        '"ok"',
        '"errors"',
        '"warnings"',
        "return 0",
        "return 1",
        "raise SystemExit(main())",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_storage_migration_validator_entrypoint_propagates_nonzero_exit_code() -> None:
    tree = ast.parse(_read_validator())

    main_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    assert len(main_defs) == 1

    main_def = main_defs[0]
    assert isinstance(main_def.returns, ast.Name)
    assert main_def.returns.id == "int"

    system_exit_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "SystemExit"
        and node.exc.args
        and isinstance(node.exc.args[0], ast.Call)
        and isinstance(node.exc.args[0].func, ast.Name)
        and node.exc.args[0].func.id == "main"
    ]
    assert len(system_exit_calls) == 1


def test_storage_integration_check_locks_env_gated_contract() -> None:
    content = _read_integration_check()

    required_snippets = [
        "STORAGE_INTEGRATION_TEST",
        "STORAGE_MIGRATION_EXECUTE",
        "STORAGE_MIGRATION_ROLLBACK",
        "--execute",
        "--rollback",
        "DATABASE_URL",
        "QDRANT_URL",
        "insightdesk_test_",
        "json.dumps",
        '"checked"',
        '"skipped"',
        '"errors"',
        '"warnings"',
        "raise SystemExit(main())",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []


def test_qdrant_backfill_runner_locks_env_gated_dry_run_contract() -> None:
    content = _read_qdrant_backfill()

    required_snippets = [
        "QDRANT_BACKFILL_EXECUTE",
        "--execute",
        "allow-dangerous-faiss-deserialization",
        "side-effect-free plan",
        "validate_qdrant_config",
        "FAISS.load_local",
        "QdrantClient",
        "create_collection",
        "upsert",
        '"remaining"',
        "json.dumps",
        "raise SystemExit(main())",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in content]
    assert missing == []
