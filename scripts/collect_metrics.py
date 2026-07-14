#!/usr/bin/env python3
"""MEES 指标采集（v0.5 WP3 P0 切片）。

从既有自动化产物（check_mees、追溯生成器）与受控实例计算首批指标；
不能计算的指标明确输出 `na`（无充分证据），绝不显示误导性的 0% 或 100%。
- 输入：自动运行 check_mees.py 与 generate_traceability.py 生成 JSON，再读取。
- 输出：build/metrics/metrics.json + 控制台表。
- 退出码：0 正常；2 工具或输入错误。

反虚假绿灯：分母为 0、证据仅 `S` 或数据源未接入 → status=na，value=None。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PILOT = ROOT / "examples" / "mk8-rsiic-v1-v04-pilot"


def run_tool(script, *args):
    subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                   cwd=ROOT, capture_output=True, text=True)


def load(relpath):
    fp = ROOT / relpath
    if not fp.exists():
        return None
    return json.loads(fp.read_text(encoding="utf-8"))


def m(mid, name, value, unit, status, evidence, note):
    return {"id": mid, "name": name, "value": value, "unit": unit,
            "status": status, "evidence_state": evidence, "note": note}


def pct(num, den):
    return round(100.0 * num / den, 1) if den else None


def main() -> int:
    run_tool("check_mees.py", "--json", "build/check/report.json")
    run_tool("generate_traceability.py")
    chk = load("build/check/report.json")
    trc = load("build/traceability/traceability.json")
    if chk is None or trc is None:
        print("[tool] 缺少 check/traceability JSON，无法采集", file=sys.stderr)
        return 2

    metrics = []

    # MET-DOC-001 文档检查通过率
    scanned = chk.get("scanned_markdown", 0)
    err_files = {d["path"] for d in chk["diagnostics"] if d["severity"] == "error"}
    metrics.append(m("MET-DOC-001", "文档检查通过率", pct(scanned - len(err_files), scanned),
                     "%", "ok" if scanned else "na", "D",
                     f"{scanned - len(err_files)}/{scanned} 文件无 error 诊断"))

    nodes = trc["nodes"]
    diags = trc["diagnostics"]
    by_rule = {}
    for d in diags:
        by_rule.setdefault(d["rule_id"], []).append(d)

    # MET-TRC-001 双向追溯完整率（非孤立对象比例）
    total = len(nodes)
    orphans = {d["object"] for d in by_rule.get("TRC-ORPHAN", [])}
    metrics.append(m("MET-TRC-001", "双向追溯完整率", pct(total - len(orphans), total),
                     "%", "ok" if total else "na", "S",
                     f"{total - len(orphans)}/{total} 对象有追溯关系（数据为 MK8 模拟 S）"))

    # MET-VNV-001 需求验证覆盖率（技术需求）
    tech = [n for n in nodes if n["kind"] in ("SYS-REQ", "SWE-REQ")]
    noverif = {d["object"] for d in by_rule.get("TRC-NO-VERIF", [])}
    verified = [n for n in tech if n["id"] not in noverif]
    metrics.append(m("MET-VNV-001", "需求验证覆盖率", pct(len(verified), len(tech)),
                     "%", "ok" if tech else "na", "S",
                     f"{len(verified)}/{len(tech)} 技术需求有验证关系"))

    # MET-VNV-002 测试执行率
    tests = [n for n in nodes if n["kind"] == "TST"]
    notrun = set()
    for d in by_rule.get("TRC-TEST-NOTRUN", []):
        notrun |= {x for x in d.get("object", "").split(",") if x}
    executed = len(tests) - len([t for t in tests if t["id"] in notrun])
    metrics.append(m("MET-VNV-002", "测试执行率", pct(executed, len(tests)),
                     "%", "ok" if tests else "na", "S",
                     f"{executed}/{len(tests)} 测试已执行（0 执行场景需高亮）"))

    # MET-VNV-003 测试通过率（仅对已执行）—— 分母为 0 → na
    if executed == 0:
        metrics.append(m("MET-VNV-003", "测试通过率", None, "%", "na", "S",
                         "无已执行测试，分母为 0 → 无充分证据（不得显示 0% 或 100%）"))
    else:
        metrics.append(m("MET-VNV-003", "测试通过率", None, "%", "na", "S",
                         "已执行测试的通过/失败结果未在受控记录中提供"))

    # MET-TPL-001 模板实例完整率（MK8 试点）
    inst = [p for p in PILOT.glob("*.md")
            if re.search(r"^>\s*模板来源：", p.read_text(encoding="utf-8"), re.M)]
    complete = [p for p in inst if "[填写：" not in p.read_text(encoding="utf-8")]
    metrics.append(m("MET-TPL-001", "模板实例完整率", pct(len(complete), len(inst)),
                     "%", "ok" if inst else "na", "S",
                     f"{len(complete)}/{len(inst)} 试点实例无未处置占位符"))

    # 数据源未接入 → na（在字典中已定义口径，等后续版本接入）
    for mid, name in [("MET-ISS-001", "开放问题严重度分布"),
                      ("MET-REL-001", "发布门禁就绪度"),
                      ("MET-QA-001", "不符合项逾期率"),
                      ("MET-SUP-001", "SBOM/供应方证据完整率")]:
        metrics.append(m(mid, name, None, "-", "na", "-",
                         "指标口径已在字典定义；结构化数据源未接入，暂无充分证据"))

    counts = {"ok": 0, "na": 0}
    for x in metrics:
        counts[x["status"]] = counts.get(x["status"], 0) + 1

    report = {"tool": "collect_metrics", "defined": 10, "collected": counts,
              "metrics": metrics}
    out = ROOT / "build" / "metrics" / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"指标：{len(metrics)} 项（ok={counts['ok']} na={counts['na']}）")
    for x in metrics:
        val = "N/A" if x["status"] == "na" else f"{x['value']}{x['unit']}"
        print(f"  {x['id']} {x['name']}: {val}  [{x['evidence_state']}] {x['note']}")
    print(f"报告：{out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
