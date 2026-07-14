#!/usr/bin/env python3
"""MEES 统一检查入口（v0.5 WP1 P0 切片）。

把仓库检查聚合为带规则编号的诊断，并输出稳定 JSON 报告。
- 输入：默认 `git ls-files` 的受控 Markdown（自动尊重 .gitignore）。
- 输出：控制台摘要 + `build/check/report.json`（Git 忽略目录）。
- 诊断字段：rule_id / severity / path / line / message / remediation。
- 退出码：0 通过；1 发现 error 级规则失败；2 工具或输入错误。

设计原则：只读、只报告；不修改工作产品；缺失/无数据明确报错，不制造虚假绿灯。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
DOCNUM_RE = re.compile(r"^>\s*文档编号：\s*(\S+)", re.MULTILINE)
EVID_RE = re.compile(r"证据状态：\s*([A-Za-z+/、,\s一-鿿]+?)\s*$", re.MULTILINE)
NAV_ENTRY_RE = re.compile(r":\s*([0-9A-Za-z_][^:\s]*\.md)\s*$")
EVID_TOKENS = {"D", "S", "P", "I"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def git_tracked(pattern: str) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", pattern],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(f"[tool] git ls-files 失败：{exc}")
    return [ROOT / line for line in out.stdout.split("\0") if line.strip()]


def diag(rule_id, severity, path, line, message, remediation):
    return {
        "rule_id": rule_id,
        "severity": severity,
        "path": rel(path) if isinstance(path, Path) else path,
        "line": line,
        "message": message,
        "remediation": remediation,
    }


def rule_links(md_files):
    out = []
    for md in md_files:
        base = md.parent
        for i, text in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for target in LINK_RE.findall(text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                clean = target.split("#")[0]
                if not clean:
                    continue
                if not (base / clean).resolve().exists():
                    out.append(diag("LINK-001", "error", md, i,
                                    f"本地链接目标不存在：{target}",
                                    "修正相对路径或补齐目标文件"))
    return out


def rule_docnum(md_files):
    out = []
    seen = {}
    for md in md_files:
        for m in DOCNUM_RE.finditer(md.read_text(encoding="utf-8")):
            num = m.group(1).strip("`")
            seen.setdefault(num, []).append(md)
    for num, files in seen.items():
        if len(files) > 1:
            out.append(diag("NUM-001", "error", files[1], 3,
                            f"文档编号重复：{num} 出现在 {', '.join(rel(f) for f in files)}",
                            "每个文档编号在仓库内必须唯一"))
    return out


def rule_mermaid(md_files):
    out = []
    for md in md_files:
        lines = md.read_text(encoding="utf-8").splitlines()
        open_fence = None
        for i, text in enumerate(lines, 1):
            stripped = text.strip()
            if stripped.startswith("```"):
                if open_fence is None:
                    open_fence = (i, stripped)
                else:
                    open_fence = None
        if open_fence is not None:
            out.append(diag("MERMAID-001", "error", md, open_fence[0],
                            "代码围栏未成对闭合",
                            "补齐结尾 ``` 围栏"))
    return out


def rule_evidence(md_files):
    out = []
    for md in md_files:
        for i, text in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            m = EVID_RE.search(text)
            if not m:
                continue
            value = m.group(1)
            letters = re.findall(r"[A-Za-z]+", value)
            bad = [t for t in letters if t.upper() not in EVID_TOKENS]
            if letters and bad:
                out.append(diag("EVID-001", "warning", md, i,
                                f"证据状态含非法令牌：{bad}（允许 D/S/P/I 及其组合）",
                                "仅使用 D/S/P/I；模拟证据不得标为 P/I"))
    return out


def rule_nav(md_files):
    out = []
    mkdocs = ROOT / "mkdocs.yml"
    if not mkdocs.exists():
        return [diag("NAV-001", "error", "mkdocs.yml", 0, "缺少 mkdocs.yml", "创建导航配置")]
    docs = ROOT / "docs"
    in_nav = False
    for i, text in enumerate(mkdocs.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"^nav:", text):
            in_nav = True
            continue
        if in_nav and re.match(r"^\S", text):
            in_nav = False
        if not in_nav:
            continue
        m = NAV_ENTRY_RE.search(text)
        if m and not (docs / m.group(1)).exists():
            out.append(diag("NAV-001", "error", "mkdocs.yml", i,
                            f"导航指向不存在的文档：{m.group(1)}",
                            "修正 nav 路径或补齐文档"))
    return out


RULES = [rule_links, rule_docnum, rule_mermaid, rule_evidence, rule_nav]


def main() -> int:
    parser = argparse.ArgumentParser(description="MEES 统一检查入口")
    parser.add_argument("--json", default="build/check/report.json",
                        help="JSON 报告输出路径（相对仓库根）")
    args = parser.parse_args()

    md_files = git_tracked("*.md")
    if not md_files:
        print("[tool] 未发现受控 Markdown 文件", file=sys.stderr)
        return 2

    diagnostics = []
    for rule in RULES:
        diagnostics.extend(rule(md_files))

    counts = {"error": 0, "warning": 0, "info": 0}
    for d in diagnostics:
        counts[d["severity"]] = counts.get(d["severity"], 0) + 1

    report = {
        "tool": "check_mees",
        "scanned_markdown": len(md_files),
        "counts": counts,
        "diagnostics": diagnostics,
    }
    out_path = ROOT / args.json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"MEES check：扫描 {len(md_files)} 个受控 Markdown；"
          f"error={counts['error']} warning={counts['warning']} info={counts['info']}")
    for d in diagnostics:
        print(f"  [{d['severity']}] {d['rule_id']} {d['path']}:{d['line']} {d['message']}")
    print(f"报告：{rel(out_path)}")

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
