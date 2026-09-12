"""Golden-set eval runner tests (offline, canned LLM)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "evals" / "run_evals.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_evals", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_score_case_keyword_and_sources_checks():
    runner = _load_runner()
    expect = {
        "keywords": ["知识库", "检索"],
        "any_of": ["架构", "摘要"],
        "sources_min": 0,
    }
    scored = runner.score_case("知识库包含文档摘要，支持关键词检索。", expect, sources_count=0)
    assert scored["score"] == 1.0
    assert scored["missing_keywords"] == []

    scored_fail = runner.score_case("完全无关的输出。", expect, sources_count=0)
    assert scored_fail["score"] < 1.0
    assert set(scored_fail["missing_keywords"]) == {"知识库", "检索"}


def test_score_case_sources_gate_fails_when_below_minimum():
    runner = _load_runner()
    scored = runner.score_case("带来源的回答。", {"keywords": [], "sources_min": 2}, sources_count=1)
    assert scored["sources_ok"] is False
    assert scored["score"] == 0.0


def test_runner_end_to_end_offline_passes_golden_set():
    result = subprocess.run(
        [sys.executable, str(RUNNER)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
