#!/usr/bin/env python3
"""MEES 追溯生成器（v0.5 WP2 P0 切片）。

从受控 Markdown 实例解析追溯对象与关系，生成双向追溯矩阵。
- 输入：默认 MK8 v0.4 试点实例目录（可用 --source 指定其它受控目录）。
- 输出：build/traceability/traceability.{json,csv,md}（Git 忽略目录）。
- 关系类型：derive（来源→派生）、trace（需求→设计→实现→测试）、verifies（测试→需求）。
- 诊断：孤立对象、被引用未定义对象、无验证链的技术需求。
- 退出码：0 无 error 级诊断；1 有 error；2 工具或输入错误。

原则：只汇总源记录中的关系，不创造缺失关系；断链进诊断，不自动补齐。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = "examples/mk8-rsiic-v1-v04-pilot"

PREFIXES = ["PGO", "PRD", "SYS-REQ", "SYS-ARC", "SWE-REQ", "SWE-ARC",
            "SWE-DD", "SWU", "TST", "CHG", "BL", "REL", "HAZ", "SIL", "SAFE-FN", "IF"]
# 基础 ID + 仅数字的斜杠兄弟简写（如 TST-MK8-001/002/003）。
ID_RE = re.compile(
    r"(?P<base>(?:" + "|".join(PREFIXES) + r")-[A-Z0-9]+-[A-Z0-9]+(?:-[A-Z0-9]+)*)"
    r"(?P<tail>(?:/[0-9]+)+)?"
)
REQ_KINDS = {"PGO", "PRD", "SYS-REQ", "SWE-REQ"}
TECH_REQ_KINDS = {"SYS-REQ", "SWE-REQ"}


def rel(path: Path) -> str:
    p = Path(path)
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def kind_of(obj_id: str) -> str:
    for p in sorted(PREFIXES, key=len, reverse=True):
        if obj_id.startswith(p + "-"):
            return p
    return "?"


def extract_ids(cell: str) -> list[str]:
    ids: list[str] = []
    for m in ID_RE.finditer(cell):
        base = m.group("base")
        ids.append(base)
        tail = m.group("tail")
        if tail:
            stem = base.rsplit("-", 1)[0]
            for seg in tail.strip("/").split("/"):
                ids.append(f"{stem}-{seg}")
    # 去重保序
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_tables(text: str):
    tables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line.lstrip().startswith("|") and "-" in nxt and re.search(r"\|?\s*:?-{2,}", nxt):
            header = split_row(line)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append(split_row(lines[j]))
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


def col_index(header, *keywords):
    for idx, h in enumerate(header):
        if any(k in h for k in keywords):
            return idx
    return None


def build_model(source: Path):
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    defined: set[str] = set()
    test_status: dict[str, str] = {}

    def add_node(obj_id, file):
        n = nodes.setdefault(obj_id, {"id": obj_id, "kind": kind_of(obj_id), "files": []})
        if rel(file) not in n["files"]:
            n["files"].append(rel(file))

    def add_edge(src, dst, etype, file):
        for s in src:
            for d in dst:
                if s != d:
                    edges.append({"from": s, "to": d, "type": etype, "source": rel(file)})

    md_files = sorted(source.rglob("*.md"))
    for md in md_files:
        for header, rows in parse_tables(md.read_text(encoding="utf-8")):
            id_idx = col_index(header, "标识")
            src_idx = col_index(header, "来源", "理由")
            tst_idx = col_index(header, "TST")
            trace_idx = col_index(header, "追溯")
            status_idx = col_index(header, "状态")
            is_matrix = (col_index(header, "需求") is not None
                         and col_index(header, "测试") is not None
                         and id_idx is None)

            for row in rows:
                cells = row + [""] * (len(header) - len(row))
                row_ids = {c: extract_ids(cells[c]) for c in range(len(header))}
                for c in row_ids.values():
                    for oid in c:
                        add_node(oid, md)

                # 定义表：含"标识"列 → 该列 ID 视为已定义
                if id_idx is not None and row_ids.get(id_idx):
                    for oid in row_ids[id_idx]:
                        defined.add(oid)
                    if src_idx is not None and row_ids.get(src_idx):
                        add_edge(row_ids[src_idx], row_ids[id_idx], "derive", md)

                # 验证表：TST + 追溯 → 测试验证需求；测试视为已定义
                if tst_idx is not None and trace_idx is not None and row_ids.get(tst_idx):
                    for t in row_ids[tst_idx]:
                        defined.add(t)
                        if status_idx is not None:
                            test_status[t] = cells[status_idx]
                    add_edge(row_ids[tst_idx], row_ids.get(trace_idx, []), "verifies", md)

                # 追溯矩阵：按列顺序在相邻非空列间连边
                if is_matrix:
                    ordered = [row_ids[c] for c in range(len(header)) if row_ids[c]]
                    for k in range(len(ordered) - 1):
                        add_edge(ordered[k], ordered[k + 1], "trace", md)

    return nodes, edges, defined, test_status


def closure(start, edges, directions):
    adj = {}
    for e in edges:
        if e["type"] in directions:
            adj.setdefault(e["from"], []).append(e["to"])
    seen, stack, path = set(), [start], []
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                path.append((cur, nxt))
                stack.append(nxt)
    return seen, path


def upstream_closure(start, edges):
    """Follow engineering relations from a verification object back upstream."""
    adj = {}
    for edge in edges:
        if edge["type"] in {"derive", "trace"}:
            adj.setdefault(edge["to"], []).append(edge["from"])
        elif edge["type"] == "verifies":
            adj.setdefault(edge["from"], []).append(edge["to"])
    seen, stack = set(), [start]
    while stack:
        current = stack.pop()
        for upstream in adj.get(current, []):
            if upstream not in seen:
                seen.add(upstream)
                stack.append(upstream)
    return seen


def build_query_pairs(nodes, edges, limit=3):
    """Build reproducible forward/reverse query pairs with a round-trip verdict."""
    candidates = sorted(
        (obj_id for obj_id in nodes if kind_of(obj_id) in REQ_KINDS),
        key=lambda obj_id: (PREFIXES.index(kind_of(obj_id)), obj_id),
    )
    pairs = []
    for start in candidates:
        forward = sorted(closure(start, edges, {"derive", "trace"})[0])
        tests = [obj_id for obj_id in forward if kind_of(obj_id) == "TST"]
        if not tests:
            continue
        reverse_start = tests[0]
        reverse = sorted(upstream_closure(reverse_start, edges))
        pairs.append({
            "forward_from": start,
            "forward_reaches": forward,
            "reverse_from": reverse_start,
            "reverse_reaches": reverse,
            "round_trip": start in reverse,
        })
        if len(pairs) == limit:
            break
    return pairs


def diagnose(nodes, edges, defined, test_status):
    diags = []
    incident = set()
    for e in edges:
        incident.add(e["from"])
        incident.add(e["to"])

    for oid, n in sorted(nodes.items()):
        if oid not in incident:
            diags.append({"rule_id": "TRC-ORPHAN", "severity": "warning", "object": oid,
                          "message": "孤立对象：无任何追溯关系",
                          "remediation": "补齐上游来源或下游设计/验证关系"})
        if oid not in defined:
            diags.append({"rule_id": "TRC-DANGLING", "severity": "warning", "object": oid,
                          "message": "被引用但未在任何定义表（标识列/验证表）中定义",
                          "remediation": "在对应过程实例中补充该对象的定义行"})

    # 技术需求是否有验证：被 verifies 边指向，或前向可达某 TST
    verified = {e["to"] for e in edges if e["type"] == "verifies"}
    for oid, n in sorted(nodes.items()):
        if n["kind"] in TECH_REQ_KINDS:
            reach, _ = closure(oid, edges, {"derive", "trace"})
            has_test = any(kind_of(x) == "TST" for x in reach) or oid in verified
            if not has_test:
                diags.append({"rule_id": "TRC-NO-VERIF", "severity": "error", "object": oid,
                              "message": "技术需求无验证关系（既无 verifies 边，也不前向可达任何 TST）",
                              "remediation": "补充需求到测试的追溯或验证用例"})

    not_run = [t for t, s in test_status.items() if s and "执行" in s and "未" in s]
    if not_run:
        diags.append({"rule_id": "TRC-TEST-NOTRUN", "severity": "info",
                      "object": ",".join(sorted(not_run)),
                      "message": f"{len(not_run)} 个测试为计划未执行；不得计入通过率",
                      "remediation": "执行后回填结果与证据，方可支撑 G5"})
    return diags


def main() -> int:
    parser = argparse.ArgumentParser(description="MEES 追溯生成器")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="受控实例目录（相对仓库根）")
    parser.add_argument("--outdir", default="build/traceability", help="输出目录（相对仓库根）")
    args = parser.parse_args()

    source = ROOT / args.source
    if not source.exists():
        print(f"[tool] 源目录不存在：{args.source}", file=sys.stderr)
        return 2

    nodes, edges, defined, test_status = build_model(source)
    if not nodes:
        print(f"[tool] 未在 {args.source} 发现追溯对象", file=sys.stderr)
        return 2
    diags = diagnose(nodes, edges, defined, test_status)

    # 演示查询
    query_pairs = build_query_pairs(nodes, edges)
    first_query = query_pairs[0] if query_pairs else {
        "forward_from": None, "forward_reaches": [],
        "reverse_from": None, "reverse_reaches": [], "round_trip": False,
    }

    counts = {"error": 0, "warning": 0, "info": 0}
    for d in diags:
        counts[d["severity"]] = counts.get(d["severity"], 0) + 1

    report = {
        "tool": "generate_traceability",
        "source": args.source,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "counts": counts,
        "nodes": list(nodes.values()),
        "edges": edges,
        "diagnostics": diags,
        "queries": {
            "forward_from": first_query["forward_from"],
            "forward_reaches": first_query["forward_reaches"],
            "reverse_from": first_query["reverse_from"],
            "reverse_reaches": first_query["reverse_reaches"],
            "query_pairs": query_pairs,
        },
    }
    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "traceability.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (outdir / "traceability.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["from", "to", "type", "source"])
        for e in edges:
            w.writerow([e["from"], e["to"], e["type"], e["source"]])
    md = [f"# 追溯矩阵（{args.source}）", "",
          f"- 对象：{len(nodes)}　关系：{len(edges)}",
          f"- 诊断：error={counts['error']} warning={counts['warning']} info={counts['info']}",
          f"- 双向查询对：{len(query_pairs)} 组", "",
          "## 双向查询", "", "| forward | reverse | round trip |", "|---|---|---|"]
    for query in query_pairs:
        md.append(
            f"| {query['forward_from']} -> {len(query['forward_reaches'])} | "
            f"{query['reverse_from']} -> {len(query['reverse_reaches'])} | "
            f"{'yes' if query['round_trip'] else 'no'} |"
        )
    md += ["", "## 关系", "", "| from | type | to |", "|---|---|---|"]
    for e in edges:
        md.append(f"| {e['from']} | {e['type']} | {e['to']} |")
    md += ["", "## 诊断", "", "| rule | severity | object | message |", "|---|---|---|---|"]
    for d in diags:
        md.append(f"| {d['rule_id']} | {d['severity']} | {d.get('object','')} | {d['message']} |")
    (outdir / "traceability.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"追溯：{len(nodes)} 对象 / {len(edges)} 关系；"
          f"error={counts['error']} warning={counts['warning']} info={counts['info']}")
    for d in diags:
        print(f"  [{d['severity']}] {d['rule_id']} {d.get('object','')} {d['message']}")
    print(f"双向查询对={len(query_pairs)}；输出：{rel(outdir)}")

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
