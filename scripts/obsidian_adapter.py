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

    def read_active(self):
        """O2：读取 Obsidian 当前活动笔记（/active/）。无实时连接时不降级 O0（O0 无活动笔记概念）。"""
        base = os.environ.get(self.config["remote_url_env"])
        token = os.environ.get(self.config["remote_token_env"])
        if not base or not token:
            self._audit("O2_ACTIVE", "active-note", "unavailable_no_connection")
            raise ObsidianAccessError("active note requires a live O2 connection; O0 has no active-note concept")
        headers = {"Authorization": f"Bearer {token}"}
        if self.transport:
            content = self.transport(base, "__active__", headers)
        else:
            request = urllib.request.Request(f"{base.rstrip('/')}/active/", headers=headers)
            with urllib.request.urlopen(request, timeout=5) as response:
                content = response.read().decode("utf-8")
        self._audit("O2_ACTIVE", "active-note", "allowed", {"sha256": hashlib.sha256(content.encode()).hexdigest()})
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


# --- CLI 运行器（O2/O3 真实试点用；证据落 build/obsidian/audit.jsonl）---

def _connected(adapter):
    return bool(os.environ.get(adapter.config["remote_url_env"]) and
                os.environ.get(adapter.config["remote_token_env"]))


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="MEES Obsidian O0-O3 适配器 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="打印配置与连接状态（不打印 token）")
    p = sub.add_parser("o0-read"); p.add_argument("path")
    p = sub.add_parser("o1-search"); p.add_argument("query")
    p = sub.add_parser("o2-read"); p.add_argument("path")
    sub.add_parser("o2-active", help="读取当前活动笔记（需实时连接）")
    p = sub.add_parser("o3-propose"); p.add_argument("path")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--content"); g.add_argument("--content-file")
    p = sub.add_parser("o3-apply"); p.add_argument("proposal_id"); p.add_argument("--confirm", required=True)
    p = sub.add_parser("o3-rollback"); p.add_argument("rollback_path")
    args = parser.parse_args(argv)

    a = ObsidianAdapter()
    proposals = a.root / "build/obsidian/proposals"
    try:
        if args.cmd == "status":
            print(json.dumps({
                "mode": a.config["mode"], "read_roots": a.config["read_roots"],
                "write_roots": a.config["write_roots"],
                "remote_write_enabled": a.config["remote_write_enabled"],
                "local_write_enabled": a.config["local_write_enabled"],
                "connected": _connected(a),
                "url_env": a.config["remote_url_env"], "token_env": a.config["remote_token_env"],
            }, ensure_ascii=False, indent=2))
        elif args.cmd == "o0-read":
            print(a.read_local(args.path))
        elif args.cmd == "o1-search":
            print("\n".join(a.search_local(args.query)) or "(no match)")
        elif args.cmd == "o2-read":
            print(a.read_remote(args.path))
        elif args.cmd == "o2-active":
            print(a.read_active())
        elif args.cmd == "o3-propose":
            content = args.content if args.content is not None else Path(args.content_file).read_text(encoding="utf-8")
            proposal = a.propose_write(args.path, content)
            proposals.mkdir(parents=True, exist_ok=True)
            (proposals / f"{proposal['proposal_id']}.json").write_text(
                json.dumps(proposal, ensure_ascii=False), encoding="utf-8")
            print(f"proposal_id: {proposal['proposal_id']}\n--- diff ---\n{proposal['diff'] or '(new file)'}")
            print(f"确认写入：o3-apply {proposal['proposal_id']} --confirm {proposal['proposal_id']}")
        elif args.cmd == "o3-apply":
            proposal = json.loads((proposals / f"{args.proposal_id}.json").read_text(encoding="utf-8"))
            rollback = a.apply_write(proposal, args.confirm)
            print(f"written; rollback record: {rollback.relative_to(a.root).as_posix()}")
        elif args.cmd == "o3-rollback":
            a.rollback(args.rollback_path)
            print("rolled back")
    except ObsidianAccessError as exc:
        print(f"[rejected] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
