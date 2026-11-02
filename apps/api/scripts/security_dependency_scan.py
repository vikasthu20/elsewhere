#!/usr/bin/env python3
"""Generate a CycloneDX 1.5 SBOM and perform an offline advisory-feed match.

This intentionally does not fetch feeds or execute package managers. Supply a
reviewed JSON advisory file to make findings; without one the report is inventory-only.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def npm_components(root: Path) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for lock in root.rglob("package-lock.json"):
        if any(part in {"node_modules", ".git"} for part in lock.parts):
            continue
        data = read_json(lock)
        packages = data.get("packages", {}) if isinstance(data, dict) else {}
        for key, item in packages.items():
            if not key or not key.startswith("node_modules/") or not isinstance(item, dict):
                continue
            name = item.get("name") or key.rsplit("node_modules/", 1)[-1]
            version = item.get("version")
            if version:
                found[("npm", name)] = component("npm", name, str(version), item.get("integrity"), str(lock.relative_to(root)))
        if not packages and isinstance(data, dict):
            deps = data.get("dependencies", {})
            def walk(items: dict[str, Any], prefix=""):
                for name, item in items.items():
                    if not isinstance(item, dict): continue
                    version = item.get("version")
                    if version: found[("npm", name)] = component("npm", name, str(version), item.get("integrity"), str(lock.relative_to(root)))
                    walk(item.get("dependencies", {}), prefix + name + "/")
            if isinstance(deps, dict): walk(deps)
    return list(found.values())


def python_components(root: Path) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    pattern = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(?:\[.*?\])?\s*==\s*([A-Za-z0-9_.+!-]+)")
    for req in root.rglob("requirements*.txt"):
        if any(part in {".venv", "venv", ".git", "node_modules"} for part in req.parts): continue
        try: lines = req.read_text(encoding="utf-8").splitlines()
        except OSError: continue
        for line in lines:
            match = pattern.match(line.split("#", 1)[0])
            if match:
                name, version = match.groups()
                found[("pypi", name.lower().replace("_", "-").replace(".", "-"))] = component("pypi", name, version, None, str(req.relative_to(root)))
    return list(found.values())


def component(ecosystem: str, name: str, version: str, integrity: str | None, source: str) -> dict[str, Any]:
    purl = f"pkg:{ecosystem}/{name}@{version}"
    return {"type": "library", "name": name, "version": version, "purl": purl, "bom-ref": purl,
            "hashes": ([{"alg": "SHA-512", "content": integrity.split("-", 1)[1]}] if integrity and integrity.startswith("sha512-") else []),
            "properties": [{"name": "elsewhere:manifest", "value": source}]}


def advisory_findings(components: list[dict[str, Any]], feed: Any) -> list[dict[str, Any]]:
    # Supported feed shape: {"advisories":[{"id","package","ecosystem","affected_versions":["1.2.3"],"severity","summary","url"}]}
    advisories = feed.get("advisories", []) if isinstance(feed, dict) else []
    findings = []
    for comp in components:
        for adv in advisories:
            if not isinstance(adv, dict): continue
            ecosystem = str(adv.get("ecosystem", "")).lower()
            package = str(adv.get("package", "")).lower()
            affected = [str(v) for v in adv.get("affected_versions", [])]
            if ecosystem == comp["purl"].split(":", 1)[1].split("/", 1)[0] and package == comp["name"].lower() and comp["version"] in affected:
                findings.append({"id": str(adv.get("id", "UNSPECIFIED")), "package": comp["name"], "version": comp["version"],
                                 "ecosystem": ecosystem, "severity": str(adv.get("severity", "unknown")),
                                 "summary": str(adv.get("summary", "")), "url": str(adv.get("url", ""))})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root to inventory")
    parser.add_argument("--output-dir", default="security-scan-output")
    parser.add_argument("--advisories", help="Reviewed local JSON advisory feed (exact-version matches)")
    args = parser.parse_args()
    root = Path(args.root).resolve(); out = Path(args.output_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
    components = npm_components(root) + python_components(root)
    components.sort(key=lambda c: (c["name"].lower(), c["version"]))
    timestamp = datetime.now(timezone.utc).isoformat()
    serial = "urn:uuid:" + hashlib.sha256((str(root) + timestamp).encode()).hexdigest()[:32]
    bom = {" bomFormat": "CycloneDX".strip(), "specVersion": "1.5", "serialNumber": serial, "version": 1,
           "metadata": {"timestamp": timestamp, "tools": [{"vendor": "Elsewhere", "name": "dependency-security-scan", "version": "1.0"}]},
           "components": components}
    feed = read_json(Path(args.advisories).resolve()) if args.advisories else None
    findings = advisory_findings(components, feed)
    report = {"generated_at": timestamp, "project_root": str(root), "component_count": len(components),
              "advisory_feed_supplied": bool(args.advisories), "matching_findings": len(findings),
              "scan_mode": "offline_exact_version_advisory_match" if args.advisories else "inventory_only_no_advisory_feed",
              "limitations": ["No network lookup or live OSV/NVD query is performed.", "Only exact versions listed in the supplied advisory feed are matched.",
                              "Unpinned requirements, transitive packages absent from lockfiles, OS packages, containers and runtime assets may be missed.",
                              "A clean report is not proof that dependencies are vulnerability-free."],
              "findings": findings}
    (out / "sbom.cyclonedx.json").write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    (out / "dependency-scan-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"components": len(components), "findings": len(findings), "output_dir": str(out), "mode": report["scan_mode"]}, indent=2))
    return 1 if findings else 0

if __name__ == "__main__":
    sys.exit(main())
