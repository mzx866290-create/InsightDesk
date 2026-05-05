"""Run the focused regression suite for the agent_core split.

This wrapper keeps the split-regression command discoverable for release and
deployment checks without requiring shell-specific glob expansion.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


DEFAULT_TEST_PATTERNS = [
    "tests/test_agent_core_split_regression.py",
    "tests/test_backend_module_compat.py",
    "tests/test_agent_core_*.py",
    "tests/test_agent_mcp_helpers.py",
    "tests/test_agent_orchestrator.py",
    "tests/test_api_agent_stream_helpers.py",
    "tests/test_api_chat_stream_helpers.py",
]


def _expand_test_patterns(patterns: list[str]) -> list[str]:
    tests: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(str(PROJECT_ROOT / pattern)))
        if matches:
            tests.extend(str(Path(match).relative_to(PROJECT_ROOT)) for match in matches)
        else:
            tests.append(pattern)
    return list(dict.fromkeys(tests))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run agent_core split compatibility and regression tests.",
    )
    parser.add_argument(
        "--pytest-arg",
        action="append",
        default=[],
        help="Extra argument passed through to pytest. Repeat as needed.",
    )
    args, passthrough_args = parser.parse_known_args()

    command = [
        sys.executable,
        "-m",
        "pytest",
        *_expand_test_patterns(DEFAULT_TEST_PATTERNS),
        *args.pytest_arg,
        *passthrough_args,
    ]

    env = os.environ.copy()
    pythonpath_entries = [str(PROJECT_ROOT), str(PROJECT_ROOT / "backend")]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

    print("Running:", " ".join(command), flush=True)
    return subprocess.call(command, cwd=PROJECT_ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
