"""Golden-set regression evals for the agent chat pipeline.

Usage:
    # offline regression (deterministic canned LLM, no network):
    python scripts/evals/run_evals.py

    # against a configured provider (LLM_PROVIDER / keys from .env):
    python scripts/evals/run_evals.py --live

    # custom case file / strict gate:
    python scripts/evals/run_evals.py --cases my_cases.jsonl --min-score 0.9

Writes a JSON report under runtime/evals/ and exits non-zero when the
average case score drops below --min-score (default 1.0).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_CASES = Path(__file__).resolve().parent / "golden_cases.jsonl"
REPORT_DIR = ROOT / "runtime" / "evals"


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        case = json.loads(line)
        if "case_id" not in case or "user_request" not in case:
            raise ValueError(f"golden case missing case_id/user_request: {line[:80]}")
        cases.append(case)
    return cases


def score_case(
    output: str,
    expect: dict[str, Any],
    *,
    sources_count: int = 0,
) -> dict[str, Any]:
    """Score one model output against the case expectations.

    Checks (each contributes equally):
    - keywords: every entry must appear (case-insensitive)
    - any_of: at least one entry must appear (when provided)
    - sources_min: minimum source count (satisfied when sources absent)
    """
    haystack = str(output or "")
    lowered = haystack.lower()
    keywords = [str(k) for k in expect.get("keywords", [])]
    any_of = [str(k) for k in expect.get("any_of", [])]
    sources_min = int(expect.get("sources_min", 0) or 0)

    missing = [k for k in keywords if k.lower() not in lowered]
    any_of_ok = (not any_of) or any(k.lower() in lowered for k in any_of)
    sources_ok = sources_count >= sources_min

    any_of_points = 1 if any_of else 0
    checks_total = len(keywords) + any_of_points + 1
    checks_passed = (
        (len(keywords) - len(missing))
        + (any_of_points if any_of_ok else 0)
        + (1 if sources_ok else 0)
    )

    return {
        "missing_keywords": missing,
        "any_of_ok": any_of_ok,
        "sources_ok": sources_ok,
        "output_chars": len(haystack),
        "score": round(checks_passed / checks_total, 4) if checks_total else 1.0,
    }


class CannedLLM:
    """Deterministic stand-in for regression runs (no network, no provider)."""

    def __init__(self, canned: str):
        self._canned = canned

    async def ainvoke(self, payload: Any) -> Any:
        return types_namespace(content=self._canned)


def types_namespace(*, content: str) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(content=content)


def build_llm(case: dict[str, Any], live: bool) -> Any:
    if not live:
        return CannedLLM(str(case.get("canned_response", "")))
    from backend.agent.providers import openai_compatible  # noqa: F401 - prove import path

    from backend.core.config_runtime import sync_runtime_secret_from_store

    sync_runtime_secret_from_store()
    from backend.agent.llm import get_llm

    return get_llm()


async def run_case(case: dict[str, Any], live: bool) -> dict[str, Any]:
    from backend.agent.builder_wrappers import FunctionCallingAgentWrapper
    from backend.agent.builder_history import _persist_output_history  # noqa: F401

    llm = build_llm(case, live)

    class _NullPipeline:
        pass

    agent = FunctionCallingAgentWrapper(
        _NullExecutor(),
        llm=llm,
        pipeline=_NullPipeline(),
        system_prompt="",
        dashboard_template=None,
        knowledge_base_enabled=bool(case.get("knowledge_base_enabled", False)),
        web_search_enabled=bool(case.get("web_search_enabled", False)),
    )

    started = time.perf_counter()
    result = await agent.ainvoke(
        {"input": case["user_request"]},
        config={"configurable": {"session_id": f"eval-{case['case_id']}", "persist_history": False}},
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    scored = score_case(
        str(result.get("output", "")),
        case.get("expect", {}),
        sources_count=len(result.get("sources", []) or []),
    )
    return {
        "case_id": case["case_id"],
        "mode": case.get("mode", "plain"),
        "elapsed_ms": elapsed_ms,
        "response_mode": str(result.get("response_mode", "")),
        **scored,
    }


class _NullExecutor:
    async def ainvoke(self, payload: Any) -> dict[str, Any]:
        return {"output": "", "sources": [], "intermediate_steps": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--live", action="store_true", help="run against a configured provider")
    parser.add_argument(
        "--min-score",
        type=float,
        default=1.0,
        help="fail the run when the average score drops below this",
    )
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    if not cases:
        print("no golden cases loaded", file=sys.stderr)
        return 2

    results = [asyncio.run(run_case(case, args.live)) for case in cases]
    average = round(sum(r["score"] for r in results) / len(results), 4)

    print("=" * 60)
    for r in results:
        status = "PASS" if r["score"] >= 1.0 else "FAIL"
        missing = f" missing={r['missing_keywords']}" if r["missing_keywords"] else ""
        print(f"[{status}] {r['case_id']}: score={r['score']} {r['elapsed_ms']}ms{missing}")
    print("=" * 60)
    print(f"average score: {average} (gate: >= {args.min_score})")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"eval-report-{int(time.time())}.json"
    report_path.write_text(
        json.dumps(
            {"average_score": average, "min_score": args.min_score, "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"report: {report_path}")

    return 0 if average >= args.min_score else 1


if __name__ == "__main__":
    raise SystemExit(main())
