#!/usr/bin/env python3
"""Apply a release policy to the JSON report produced by security_dependency_scan.py."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

SEVERITY = {"critical": 4, "high": 3, "moderate": 2, "medium": 2, "low": 1, "unknown": 0}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="security-scan-output/dependency-scan-report.json")
    parser.add_argument("--fail-on-severity", choices=["critical", "high", "moderate", "low"], default="high")
    parser.add_argument("--max-findings", type=int, default=0)
    parser.add_argument("--require-advisory-feed", action="store_true")
    args = parser.parse_args()
    try:
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"SECURITY GATE ERROR: cannot read scan report: {exc}", file=sys.stderr)
        return 2
    if not isinstance(report, dict) or not isinstance(report.get("findings"), list):
        print("SECURITY GATE ERROR: report schema is invalid", file=sys.stderr)
        return 2
    if args.require_advisory_feed and not report.get("advisory_feed_supplied"):
        print("SECURITY GATE BLOCKED: no advisory feed was supplied; inventory-only is not a security scan.")
        return 2
    threshold = SEVERITY[args.fail_on_severity]
    blocking = [f for f in report["findings"] if isinstance(f, dict)
                and SEVERITY.get(str(f.get("severity", "unknown")).lower(), 0) >= threshold]
    print(json.dumps({"threshold": args.fail_on_severity, "blocking_findings": len(blocking),
        "allowed_findings": args.max_findings, "decision": "pass" if len(blocking) <= args.max_findings else "block",
        "blocking": [{"id": f.get("id"), "package": f.get("package"), "version": f.get("version"),
                      "severity": f.get("severity")} for f in blocking]}, indent=2))
    return 1 if len(blocking) > args.max_findings else 0

if __name__ == "__main__":
    raise SystemExit(main())
