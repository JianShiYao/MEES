#!/usr/bin/env python3
"""Deterministic, read-only runtime for the six MEES v0.6 Agent slices."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_DIR = ROOT / "agents" / "protocols"
ALLOWED_INPUT_ROOTS = ("docs/", "examples/", "build/")
ID_PATTERNS = {
    "requirement": re.compile(r"\b(?:PGO|PRD|SYS-REQ|SWE-REQ)-[A-Z0-9-]+\b"),
    "architecture": re.compile(r"\b(?:SYS-ARC|SWE-ARC|SWE-DD|IF)-[A-Z0-9-]+\b"),
    "test": re.compile(r"\bTST-[A-Z0-9-]+\b"),
    "aspice": re.compile(r"\b(?:SYS|SWE|SUP|MAN|ACQ)\.[0-9]+\b"),
}


class AgentInputError(ValueError):
    pass


def controlled_path(relative: str) -> Path:
    normalized = relative.replace("\\", "/")
    if not normalized.startswith(ALLOWED_INPUT_ROOTS):
        raise AgentInputError(f"input outside allowlist: {relative}")
    candidate = (ROOT / normalized).resolve()
    if ROOT.resolve() not in candidate.parents:
        raise AgentInputError(f"path traversal rejected: {relative}")
    if not candidate.is_file():
        raise AgentInputError(f"input does not exist: {relative}")
    return candidate


def load_protocol(agent: str) -> dict:
    path = PROTOCOL_DIR / f"{agent}.json"
    if not path.is_file():
        raise AgentInputError(f"unknown agent: {agent}")
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(agent: str, texts: list[str]) -> tuple[dict, list[dict]]:
    combined = "\n".join(texts)
    findings = []
    summary = {"input_count": len(texts), "character_count": len(combined)}
    if agent in ID_PATTERNS:
        ids = sorted(set(ID_PATTERNS[agent].findall(combined)))
        summary["object_count"] = len(ids)
        summary["sample_objects"] = ids[:10]
        if not ids:
            findings.append({"severity": "major", "rule": "AGT-OBJECT-001", "message": "No expected controlled object identifier found."})
    elif agent == "review":
        unchecked = len(re.findall(r"^\s*- \[ \]", combined, re.MULTILINE))
        summary["unchecked_item_count"] = unchecked
        if unchecked:
            findings.append({"severity": "general", "rule": "AGT-REVIEW-001", "message": f"{unchecked} checklist item(s) remain open."})
    elif agent == "metrics":
        documents = [json.loads(text) for text in texts]
        metrics = [item for document in documents for item in document.get("metrics", [])]
        na = [item.get("id") for item in metrics if item.get("status") == "na"]
        summary.update({"metric_count": len(metrics), "na_count": len(na), "na_metrics": na})
        if na:
            findings.append({"severity": "general", "rule": "AGT-METRIC-001", "message": f"{len(na)} metric(s) are N/A and need human interpretation."})
    if agent == "test" and "未执行" in combined:
        findings.append({"severity": "major", "rule": "AGT-TEST-001", "message": "Planned tests are not executed; release recommendation must remain No-Go."})
    return summary, findings


def run_request(request: dict, audit_path: Path | None = None) -> dict:
    required = {"run_id", "agent", "task", "inputs"}
    missing = sorted(required - request.keys())
    if missing:
        raise AgentInputError(f"missing fields: {', '.join(missing)}")
    protocol = load_protocol(request["agent"])
    if not request["inputs"]:
        raise AgentInputError("at least one input is required")
    paths, texts, states = [], [], []
    for item in request["inputs"]:
        if item.get("evidence_state") not in {"D", "S"}:
            raise AgentInputError("Agent inputs are limited to D/S evidence states")
        path = controlled_path(item["path"])
        paths.append(path.relative_to(ROOT).as_posix())
        texts.append(path.read_text(encoding="utf-8"))
        states.append(item["evidence_state"])
    summary, findings = analyze(request["agent"], texts)
    result = {
        "schema_version": "1.0", "run_id": request["run_id"],
        "agent": request["agent"], "protocol_version": protocol["version"],
        "status": "completed", "decision": "human_review_required",
        "evidence_state": "S" if "S" in states else "D",
        "human_owner": protocol["human_owner"], "inputs": paths,
        "input_digest": hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest(),
        "task": request["task"], "summary": summary, "findings": findings,
        "prohibited_actions": protocol["forbidden_actions"],
    }
    if audit_path:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit = {key: result[key] for key in ("run_id", "agent", "status", "decision", "evidence_state", "input_digest")}
        audit["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit, ensure_ascii=False) + "\n")
    return result
