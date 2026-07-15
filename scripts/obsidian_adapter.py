#!/usr/bin/env python3
"""Obsidian O0-O3 adapter with allowlists, preview, confirmation and rollback."""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ObsidianAccessError(ValueError):
    pass


class ObsidianAdapter:
    def __init__(self, root=ROOT, config=None, transport=None):
        self.root = Path(root).resolve()
        self.config = config or json.loads((self.root / "config/obsidian_integration.json").read_text(encoding="utf-8"))
        self.transport = transport

    def _path(self, relative, roots):
        normalized = str(relative).replace("\\", "/").lstrip("/")
        allowed = any(normalized == root or normalized.startswith(root.rstrip("/") + "/") for root in roots)
        if not allowed:
            raise ObsidianAccessError(f"path outside allowlist: {relative}")
        target = (self.root / normalized).resolve()
        if self.root not in target.parents:
            raise ObsidianAccessError(f"path traversal rejected: {relative}")
        return target

    def _audit(self, action, target, outcome, detail=None):
        path = self.root / self.config["audit_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "action": action, "target": str(target).replace("\\", "/"), "outcome": outcome,
        }
        if detail:
            event["detail"] = detail
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_local(self, relative):
        path = self._path(relative, self.config["read_roots"])
        text = path.read_text(encoding="utf-8")
        self._audit("O0_READ", relative, "allowed", {"sha256": hashlib.sha256(text.encode()).hexdigest()})
        return text

    def search_local(self, query):
        matches = []
        for root in self.config["read_roots"]:
            base = self._path(root, self.config["read_roots"])
            if not base.exists():
                continue
            for path in base.rglob("*.md"):
                text = path.read_text(encoding="utf-8")
                if query.casefold() in text.casefold():
                    matches.append(path.relative_to(self.root).as_posix())
        self._audit("O1_SEARCH", "selected_roots", "allowed", {"query_sha256": hashlib.sha256(query.encode()).hexdigest(), "match_count": len(matches)})
        return sorted(matches)

    def read_remote(self, relative):
        self._path(relative, self.config["read_roots"])
        base = os.environ.get(self.config["remote_url_env"])
        token = os.environ.get(self.config["remote_token_env"])
        if not base or not token:
            self._audit("O2_READ", relative, "degraded_to_O0")
            return self.read_local(relative)
        headers = {"Authorization": f"Bearer {token}"}
        if self.transport:
            content = self.transport(base, relative, headers)
        else:
            request = urllib.request.Request(f"{base.rstrip('/')}/vault/{relative}", headers=headers)
            with urllib.request.urlopen(request, timeout=5) as response:
                content = response.read().decode("utf-8")
        self._audit("O2_READ", relative, "allowed", {"sha256": hashlib.sha256(content.encode()).hexdigest()})
        return content

    def propose_write(self, relative, content):
        if not self.config.get("local_write_enabled"):
            raise ObsidianAccessError("O3 local write is disabled")
        path = self._path(relative, self.config["write_roots"])
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        proposal_id = hashlib.sha256(f"{relative}\0{before}\0{content}".encode()).hexdigest()[:16]
        proposal = {
            "proposal_id": proposal_id, "target": str(relative).replace("\\", "/"),
            "before": before, "before_existed": path.exists(), "after": content,
            "diff": "".join(difflib.unified_diff(before.splitlines(True), content.splitlines(True), fromfile="before", tofile="after")),
        }
        self._audit("O3_PROPOSE", relative, "previewed", {"proposal_id": proposal_id})
        return proposal

    def apply_write(self, proposal, confirmation):
        if confirmation != proposal["proposal_id"]:
            self._audit("O3_WRITE", proposal["target"], "rejected", {"reason": "confirmation_mismatch"})
            raise ObsidianAccessError("explicit confirmation does not match proposal")
        path = self._path(proposal["target"], self.config["write_roots"])
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != proposal["before"]:
            raise ObsidianAccessError("target changed after preview")
        rollback = self.root / "build/obsidian/rollback" / f"{proposal['proposal_id']}.json"
        rollback.parent.mkdir(parents=True, exist_ok=True)
        rollback.write_text(json.dumps({
            "target": proposal["target"], "content": current,
            "existed": proposal["before_existed"],
        }, ensure_ascii=False), encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            handle.write(proposal["after"])
            temporary = Path(handle.name)
        temporary.replace(path)
        self._audit("O3_WRITE", proposal["target"], "allowed", {"proposal_id": proposal["proposal_id"], "rollback": rollback.relative_to(self.root).as_posix()})
        return rollback

    def rollback(self, rollback_path):
        record_path = self._path(rollback_path, ["build/obsidian/rollback"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        target = self._path(record["target"], self.config["write_roots"])
        if record["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(record["content"], encoding="utf-8")
        elif target.exists():
            target.unlink()
        self._audit("O3_ROLLBACK", record["target"], "allowed")
