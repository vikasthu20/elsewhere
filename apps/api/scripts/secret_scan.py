#!/usr/bin/env python3
"""Local secret scanner for tracked working-tree files and reachable Git history.

Findings are redacted: the scanner never prints matched secret values.
For production CI, pair this with Gitleaks (workflow included in Step 87).
"""
from __future__ import annotations
import argparse
import fnmatch
import math
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Generic credential assignment", re.compile(
        r"""(?i)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|password|passwd|secret)\b\s*[:=]\s*['"]?([A-Za-z0-9_./+=-]{16,})"""
    )),
]
DEFAULT_IGNORES = [".git/**", "**/__pycache__/**", "**/node_modules/**",
                   "**/.venv/**", "**/venv/**", "**/dist/**", "**/build/**"]

def entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {c: value.count(c) for c in set(value)}
    return -sum((n / len(value)) * math.log2(n / len(value)) for n in counts.values())

def ignored(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, p) or fnmatch.fnmatch("/" + normalized, p)
               for p in patterns)

def inspect_text(text: str, source: str, findings: set[tuple[str, str]]) -> None:
    for line_no, line in enumerate(text.splitlines(), 1):
        for label, pattern in PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            value = match.group(1) if label == "Generic credential assignment" else match.group(0)
            # Skip obvious placeholders and low-entropy documentation examples.
            lowered = value.lower()
            if any(word in lowered for word in ("example", "placeholder", "your_", "changeme", "dummy", "xxxx")):
                continue
            if label == "Generic credential assignment" and entropy(value) < 3.5:
                continue
            findings.add((source, f"{line_no}: {label}"))

def git_output(args: list[str], cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--history", action="store_true",
                        help="Also inspect reachable Git commit patches (may take time).")
    parser.add_argument("--ignore-file", default=".secretscanignore")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        tracked = git_output(["git", "ls-files", "-z"], root).split("\0")
    except RuntimeError as exc:
        print(f"SECRET SCAN ERROR: {exc}", file=sys.stderr)
        return 2
    ignores = list(DEFAULT_IGNORES)
    ignore_path = root / args.ignore_file
    if ignore_path.exists():
        ignores.extend(line.strip() for line in ignore_path.read_text().splitlines()
                       if line.strip() and not line.lstrip().startswith("#"))
    findings: set[tuple[str, str]] = set()
    for relative in filter(None, tracked):
        if ignored(relative, ignores):
            continue
        path = root / relative
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        inspect_text(content, relative, findings)
    if args.history:
        try:
            patch = git_output(["git", "log", "--all", "--format=", "--patch"], root)
        except RuntimeError as exc:
            print(f"SECRET SCAN ERROR: history scan failed: {exc}", file=sys.stderr)
            return 2
        inspect_text(patch, "git-history", findings)
    if findings:
        print(f"SECRET SCAN FAILED: {len(findings)} potential finding(s). Values are redacted.")
        for source, detail in sorted(findings):
            print(f"- {source}: {detail}")
        print("Rotate/revoke exposed credentials; remove them from active config and review Git history.")
        return 1
    print("SECRET SCAN PASSED: no matches from the configured patterns.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
