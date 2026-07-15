#!/usr/bin/env python3
"""Run the complete MEES verification pipeline and write one stable JSON report."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="MEES full verification entry point")
    parser.add_argument("--allow-npx", action="store_true", help="Allow pinned Mermaid CLI via npx")
    parser.add_argument("--json", default="build/v06/all-checks.json")
    args = parser.parse_args()

    py = sys.executable
    mermaid = [py, "scripts/check_mermaid.py"]
    if args.allow_npx:
        mermaid.append("--allow-npx")
    steps = [
        ("unit_tests", [py, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
        ("markdown_links", [py, "scripts/check_markdown_links.py"]),
        ("template_assets", [py, "scripts/check_template_assets.py"]),
        ("mees_rules", [py, "scripts/check_mees.py", "--json", "build/checks/mees.json"]),
        ("mermaid_render", mermaid),
        ("trace_mk8", [py, "scripts/generate_traceability.py", "--outdir", "build/traceability"]),
        ("trace_ess", [py, "scripts/generate_traceability.py", "--source", "examples/ess-demo-pilot", "--outdir", "build/traceability-ess"]),
        ("metrics", [py, "scripts/collect_metrics.py"]),
        ("dashboard", [py, "scripts/generate_dashboard.py"]),
        ("agent_pilot", [py, "scripts/run_agent_pilot.py"]),
        ("mkdocs_strict", [py, "-m", "mkdocs", "build", "--strict", "--site-dir", "build/site"]),
    ]

    results = []
    overall = 0
    for name, command in steps:
        print(f"\n== {name} ==", flush=True)
        completed = subprocess.run(
            command, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        console_encoding = sys.stdout.encoding or "utf-8"
        safe_output = completed.stdout.encode(console_encoding, errors="replace").decode(console_encoding)
        print(safe_output, end="")
        results.append({
            "name": name,
            "status": "passed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
        })
        if completed.returncode != 0:
            overall = 1

    report = {
        "tool": "run_all_checks", "schema_version": "1.0",
        "status": "passed" if overall == 0 else "failed",
        "step_count": len(results), "steps": results,
    }
    target = ROOT / args.json
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMEES full verification: {report['status']}; report={args.json}")
    return overall


if __name__ == "__main__":
    sys.exit(main())
