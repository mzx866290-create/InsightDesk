#!/usr/bin/env python3
"""Lightweight repository secret scanner for CI and local checks.

This scanner is intentionally conservative: it focuses on likely committed
secrets in tracked files and allows obvious placeholders in templates.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SENSITIVE_NAME_RE = re.compile(
    r"(api[_-]?key|client[_-]?secret|secret|password|credential|private[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|auth[_-]?token|bearer[_-]?token)",
    re.IGNORECASE,
)
ASSIGNMENT_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_\-]*)\s*[:=]\s*(?P<value>.+?)\s*,?\s*$",
    re.IGNORECASE,
)
GENERIC_SECRET_RE = re.compile(
    r"(?P<value>(?:sk-[A-Za-z0-9]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9_]{30,}|"
    r"glpat-[A-Za-z0-9_\-]{20,}|"
    r"AIza[A-Za-z0-9_\-]{30,}|"
    r"ya29\.[A-Za-z0-9_\-]{20,}|"
    r"tvly-[A-Za-z0-9_\-]{20,}))",
)
JWT_RE = re.compile(
    r"(?P<value>eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})",
)

PLACEHOLDER_MARKERS = (
    "your_",
    "your-",
    "replace",
    "example",
    "changeme",
    "change-me",
    "dummy",
    "placeholder",
    "local",
    "test",
    "mock",
    "fake",
    "fixture",
    "sample",
    "none",
    "null",
    "<",
    "${",
)
SAFE_EMPTY_VALUES = {"", "''", '""'}
TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
IGNORED_SUFFIXES = {".lock"}
IGNORED_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
IGNORED_PATHS = {Path("tests/test_scan_secrets.py")}
IGNORED_PARTS = {
    ".git",
    "node_modules",
    "venv",
    "venv312",
    ".venv",
    "dist",
    "test-results",
    "playwright-report",
}
CODE_EXPRESSION_MARKERS = ("(", ")", "{", "}", "[", "]", "=>", "lambda", "Call", "ctx.", "self.", "read", "str(")


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int
    reason: str
    preview: str


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    frequencies = {char: value.count(char) for char in set(value)}
    return -sum((count / len(value)) * math.log2(count / len(value)) for count in frequencies.values())


def strip_quotes(value: str) -> str:
    value = value.strip()
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        value = value[1:-1].strip()
    return value


def is_placeholder(value: str) -> bool:
    normalized = strip_quotes(value).lower()
    if normalized in SAFE_EMPTY_VALUES:
        return True
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def mask(value: str) -> str:
    value = strip_quotes(value)
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def should_scan(path: Path) -> bool:
    if path in IGNORED_PATHS:
        return False
    if any(part in IGNORED_PARTS for part in path.parts):
        return False
    if path.name in IGNORED_NAMES or path.suffix.lower() in IGNORED_SUFFIXES:
        return False
    if path.name in {".env", ".env.local"}:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.startswith(".env")


def run_git_ls_files(*args: str) -> list[Path]:
    result = subprocess.run(["git", "ls-files", "-z", *args], check=True, capture_output=True)
    return [Path(item.decode("utf-8", errors="replace")) for item in result.stdout.split(b"\0") if item]


def list_files(include_untracked: bool) -> list[Path]:
    paths = run_git_ls_files()
    if include_untracked:
        paths.extend(run_git_ls_files("--others", "--exclude-standard"))
    return sorted({path for path in paths if should_scan(path)})


def find_line_issues(path: Path, line: str, line_number: int) -> list[Finding]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return []

    findings: list[Finding] = []
    assignment = ASSIGNMENT_RE.match(line)
    if assignment:
        name = assignment.group("name")
        env_style_name = name.upper() == name and ("_" in name or path.name.startswith(".env"))
        value = strip_quotes(assignment.group("value"))
        if env_style_name and SENSITIVE_NAME_RE.search(name) and not is_placeholder(value):
            looks_like_literal = not any(marker in value for marker in CODE_EXPRESSION_MARKERS)
            if looks_like_literal and len(value) >= 12 and (shannon_entropy(value) >= 3.0 or len(value) >= 24):
                findings.append(
                    Finding(
                        path=path,
                        line_number=line_number,
                        reason=f"sensitive assignment `{name}`",
                        preview=f"{name}={mask(value)}",
                    ),
                )

    for pattern_name, pattern in (("token-like literal", GENERIC_SECRET_RE), ("jwt literal", JWT_RE)):
        for match in pattern.finditer(line):
            value = match.group("value")
            if not is_placeholder(value):
                findings.append(
                    Finding(
                        path=path,
                        line_number=line_number,
                        reason=pattern_name,
                        preview=mask(value),
                    ),
                )
    return findings


def scan_file(path: Path) -> list[Finding]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    except OSError as exc:
        return [Finding(path=path, line_number=0, reason=f"failed to read file: {exc}", preview="")]

    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        findings.extend(find_line_issues(path, line, line_number))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan repository files for likely committed secrets.")
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Also scan untracked, non-ignored files. CI normally scans tracked files only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings: list[Finding] = []
    for path in list_files(include_untracked=args.include_untracked):
        findings.extend(scan_file(path))

    if not findings:
        print("Secret scan passed: no likely committed secrets found.")
        return 0

    print("Secret scan failed: likely committed secrets found.", file=sys.stderr)
    for finding in findings:
        location = f"{finding.path}:{finding.line_number}" if finding.line_number else str(finding.path)
        print(f"- {location}: {finding.reason} ({finding.preview})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
