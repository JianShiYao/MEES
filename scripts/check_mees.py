#!/usr/bin/env python3
"""MEES 统一检查入口（v0.5 WP1 P0 切片）。

把仓库检查聚合为带规则编号的诊断，并输出稳定 JSON 报告。
- 输入：默认 Git 已跟踪和未忽略的新 Markdown（自动尊重 .gitignore）。
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
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
# 映射类文档标题特征（NUM-002）：新增此类文档必须用 MEES-MAP-*，不得挂 LIF。
MAP_TITLE_RE = re.compile(r"(过程映射|详细映射|跨标准.*矩阵|差距与行动项)")
# grandfather：v0.3.0 已发布、逻辑属映射类但保留 LIF 编号（见 02_文档与编号规范 §4.1）。
GRANDFATHER_MAP_LIF = {
    "MEES-LIF-004", "MEES-LIF-005", "MEES-LIF-006",
    "MEES-LIF-007", "MEES-LIF-008", "MEES-LIF-009",
}
V051_BASELINE_DOCS = (
    "docs/00_Introduction/06_v0.5自动化与度量建设计划.md",
    "docs/05_Test_Engineering/嵌入式目标级验证方法.md",
    "docs/07_Functional_Safety/ESS功能安全管理过程.md",
    "docs/07_Functional_Safety/储能功能安全_IEC61508_UL9540A映射.md",
    "docs/11_Process_Management/v0.5基线评审记录.md",
    "docs/12_Metrics/指标字典.md",
    "docs/13_Templates/v0.4模板目录与使用规则.md",
    "docs/15_Case_Study/v0.5_WP1_WP2自动化与追溯走查.md",
    "docs/15_Case_Study/v0.5_WP6_ESS安全方法走查.md",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def git_tracked(pattern: str) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", pattern],
            cwd=ROOT, capture_output=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(f"[tool] git ls-files 失败：{exc}")
    return [ROOT / line for line in out.stdout.decode("utf-8").split("\0") if line.strip()]


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


def rule_docs_scope(md_files):
    """docs/ 内文档不得链接到站点外（MkDocs --strict 会拒绝），与严格构建对齐。"""
    out = []
    docs_dir = (ROOT / "docs").resolve()
    for md in md_files:
        try:
            md.resolve().relative_to(docs_dir)
        except ValueError:
            continue
        base = md.parent
        for i, text in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for target in LINK_RE.findall(text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                clean = target.split("#")[0]
                if not clean:
                    continue
                resolved = (base / clean).resolve()
                if not resolved.exists():
                    continue  # 缺失由 LINK-001 负责
                try:
                    resolved.relative_to(docs_dir)
                except ValueError:
                    out.append(diag("LINK-002", "error", md, i,
                                    f"docs 内文档链接指向站点外：{target}",
                                    "改为代码引用或指向 docs/ 内文档；MkDocs --strict 拒绝站点外链接"))
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


def rule_docnum_class(md_files):
    """NUM-002：映射类文档（标题含过程映射/详细映射/跨标准矩阵/差距行动项）必须用
    MEES-MAP-*，不得挂 LIF；grandfather 集合（已发布）除外。防止 LIF 编号再次泛化。"""
    out = []
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        title_m = H1_RE.search(text)
        num_m = DOCNUM_RE.search(text)
        if not title_m or not num_m:
            continue
        title = title_m.group(1)
        num = num_m.group(1).strip("`")
        if "总览" in title or not MAP_TITLE_RE.search(title):
            continue
        if num.startswith("MEES-LIF-") and num not in GRANDFATHER_MAP_LIF:
            out.append(diag("NUM-002", "error", md, 1,
                            f"映射类文档使用了 LIF 编号：{num}（{title}）",
                            "新增映射/矩阵/差距台账须用 MEES-MAP-*；grandfather 见 02_文档与编号规范 §4.1"))
    return out


def rule_fences(md_files):
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
            out.append(diag("FENCE-001", "error", md, open_fence[0],
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


def rule_baseline_lifecycle(md_files):
    del md_files
    out = []
    expected_version = "v0.5.1"
    expected_status = "已批准（内部基线）"
    expected_updated = "2026-07-15"
    for relative_path in V051_BASELINE_DOCS:
        path = ROOT / relative_path
        if not path.exists():
            out.append(
                diag(
                    "BASELINE-001",
                    "error",
                    relative_path,
                    0,
                    "v0.5.1 内部基线缺少受控文档",
                    "补齐基线文档或修订受控清单",
                )
            )
            continue
        content = path.read_text(encoding="utf-8")
        version = re.search(r"^> 版本：(.+)$", content, re.MULTILINE)
        status = re.search(r"^> 状态：(.+)$", content, re.MULTILINE)
        updated = re.search(r"^> 最后更新：(.+)$", content, re.MULTILINE)
        actual_version = version.group(1).strip() if version else None
        actual_status = status.group(1).strip() if status else None
        actual_updated = updated.group(1).strip() if updated else None
        if actual_version != expected_version:
            out.append(
                diag(
                    "BASELINE-001",
                    "error",
                    path,
                    4,
                    f"基线版本应为 {expected_version}，实际为 {actual_version}",
                    "同步文档头部版本与批准基线版本",
                )
            )
        if actual_status != expected_status:
            out.append(
                diag(
                    "BASELINE-001",
                    "error",
                    path,
                    5,
                    f"基线状态应为 {expected_status}，实际为 {actual_status}",
                    "同步文档头部状态与 V5.1-G1 批准决定",
                )
            )
        if actual_updated != expected_updated:
            out.append(
                diag(
                    "BASELINE-001",
                    "error",
                    path,
                    7,
                    f"基线最后更新日期应为 {expected_updated}，实际为 {actual_updated}",
                    "同步文档头部最后更新日期与基线批准日期",
                )
            )
    return out


RULES = [
    rule_links,
    rule_docs_scope,
    rule_docnum,
    rule_docnum_class,
    rule_fences,
    rule_evidence,
    rule_nav,
    rule_baseline_lifecycle,
]


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
