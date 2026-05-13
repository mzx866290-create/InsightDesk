from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "scan_secrets.py"


def run_git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def run_scanner(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_scan_secrets_allows_placeholders(tmp_path: Path) -> None:
    run_git(tmp_path, "init")
    sample = tmp_path / ".env.example"
    sample.write_text(
        "\n".join(
            [
                "OPENROUTER_API_KEY=your_openrouter_api_key_here",
                "SHARE_LINK_SECRET=replace-with-32-plus-random-chars",
                "OIDC_CLIENT_SECRET=",
            ],
        ),
        encoding="utf-8",
    )
    run_git(tmp_path, "add", ".env.example")

    result = run_scanner(tmp_path)

    assert result.returncode == 0
    assert "Secret scan passed" in result.stdout


def test_scan_secrets_blocks_realistic_token_literals(tmp_path: Path) -> None:
    run_git(tmp_path, "init")
    sample = tmp_path / "settings.env"
    sample.write_text(
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890\n",
        encoding="utf-8",
    )
    run_git(tmp_path, "add", "settings.env")

    result = run_scanner(tmp_path)

    assert result.returncode == 1
    assert "settings.env:1" in result.stderr
    assert "OPENAI_API_KEY" in result.stderr


def test_scan_secrets_can_scan_untracked_files(tmp_path: Path) -> None:
    run_git(tmp_path, "init")
    sample = tmp_path / "local.env"
    sample.write_text(
        "TAVILY_API_KEY=tvly-abcdefghijklmnopqrstuvwxyz123456\n",
        encoding="utf-8",
    )

    result = run_scanner(tmp_path, "--include-untracked")

    assert result.returncode == 1
    assert "local.env:1" in result.stderr
