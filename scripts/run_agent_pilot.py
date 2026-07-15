#!/usr/bin/env python3
"""Run all six Agent slices against the MK8 simulated pilot."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from agent_runtime import ROOT, run_request

PILOT = "examples/mk8-rsiic-v1-v04-pilot"
CASES = {
    "requirement": f"{PILOT}/03_Requirements.md",
    "architecture": f"{PILOT}/04_Architecture.md",
    "review": f"{PILOT}/06_Release_Decision.md",
    "test": f"{PILOT}/05_Verification.md",
    "aspice": "docs/11_Process_Management/ASPICE_ISO_IEC_33020过程映射表.md",
    "metrics": "build/metrics/metrics.json",
}


def main() -> int:
    if not (ROOT / CASES["metrics"]).is_file():
        print("[pilot] run collect_metrics.py first", file=sys.stderr)
        return 2
    outdir = ROOT / "build/agent-pilot"
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for agent, path in CASES.items():
        request = {
            "run_id": f"V06-MK8-{agent.upper()}", "agent": agent,
            "task": "MK8 v0.6 reproducible assisted walkthrough",
            "inputs": [{"path": path, "evidence_state": "S"}],
        }
        result = run_request(request, outdir / "audit.jsonl")
        (outdir / f"{agent}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        results.append({
            "agent": agent, "status": result["status"],
            "decision": result["decision"], "finding_count": len(result["findings"]),
        })
    summary = {
        "schema_version": "1.0", "pilot": "MK8-RSIIC-V1", "evidence_state": "S",
        "release_decision": "No-Go",
        "release_reason": "Target tests remain planned but unexecuted; Agent output cannot approve a gate.",
        "agent_count": len(results), "results": results,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BMS Agent pilot: {len(results)} agents; release=No-Go; build/agent-pilot/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
