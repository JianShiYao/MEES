#!/usr/bin/env python3
"""MEES 静态 Dashboard 生成器（v0.5 WP4 P0 切片）。

运行 collect_metrics（其内部链式运行 check_mees 与追溯生成器），读取三份 JSON，
渲染自包含静态 HTML 到 build/dashboard/index.html。无服务端、无数据库、无外部依赖。
- 每个汇总值可回溯到源 JSON 与源记录。
- 显著标注 MK8/ESS 模拟证据（S）；N/A 明确区别于 0% 与 100%。
- 退出码：0 正常；2 工具或输入错误。
"""
from __future__ import annotations

import datetime
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(relpath):
    fp = ROOT / relpath
    return json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else None


def git_head():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def esc(x):
    return html.escape(str(x))


def rows(items, cells):
    return "\n".join("<tr>" + "".join(f"<td>{c}</td>" for c in cells(i)) + "</tr>" for i in items)


def main() -> int:
    subprocess.run([sys.executable, str(SCRIPTS / "collect_metrics.py")],
                   cwd=ROOT, capture_output=True, text=True)
    chk = load("build/check/report.json")
    trc = load("build/traceability/traceability.json")
    met = load("build/metrics/metrics.json")
    if not (chk and trc and met):
        print("[tool] 缺少 check/traceability/metrics JSON", file=sys.stderr)
        return 2

    head = git_head()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 证据分布
    evid = {}
    for m in met["metrics"]:
        evid[m["evidence_state"]] = evid.get(m["evidence_state"], 0) + 1

    def metric_cell(m):
        if m["status"] == "na":
            return '<span class="na">N/A</span>'
        return f'<b>{esc(m["value"])}{esc(m["unit"])}</b>'

    metrics_rows = "\n".join(
        f'<tr><td><code>{esc(m["id"])}</code></td><td>{esc(m["name"])}</td>'
        f'<td>{metric_cell(m)}</td><td><span class="ev ev-{esc(m["evidence_state"])}">{esc(m["evidence_state"])}</span></td>'
        f'<td>{esc(m["note"])}</td></tr>'
        for m in met["metrics"])

    chk_rows = rows(chk["diagnostics"],
                    lambda d: (f'<span class="sev sev-{esc(d["severity"])}">{esc(d["severity"])}</span>',
                               f'<code>{esc(d["rule_id"])}</code>',
                               f'{esc(d["path"])}:{esc(d["line"])}', esc(d["message"]))) \
        or '<tr><td colspan="4">无诊断</td></tr>'

    trc_diag_rows = rows(trc["diagnostics"],
                         lambda d: (f'<span class="sev sev-{esc(d["severity"])}">{esc(d["severity"])}</span>',
                                    f'<code>{esc(d["rule_id"])}</code>',
                                    esc(d.get("object", "")), esc(d["message"]))) \
        or '<tr><td colspan="4">无诊断</td></tr>'

    q = trc["queries"]
    page = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MEES Dashboard — {esc(head)}</title>
<style>
:root{{color-scheme:light dark}}
body{{font-family:system-ui,"Segoe UI",sans-serif;margin:0;padding:1.2rem;line-height:1.5}}
h1{{font-size:1.3rem;margin:.2rem 0}} h2{{font-size:1.05rem;margin:1.4rem 0 .4rem;border-bottom:1px solid #8884;padding-bottom:.2rem}}
.banner{{background:#f0a; background:#ffb020; color:#111; padding:.6rem .9rem;border-radius:6px;font-weight:600;margin:.6rem 0}}
.meta{{color:#888;font-size:.85rem}}
table{{border-collapse:collapse;width:100%;font-size:.85rem;margin:.3rem 0;overflow-x:auto;display:block}}
th,td{{border:1px solid #8884;padding:.25rem .5rem;text-align:left;vertical-align:top}}
th{{background:#8882}}
code{{font-size:.8rem}}
.cards{{display:flex;flex-wrap:wrap;gap:.6rem;margin:.4rem 0}}
.card{{border:1px solid #8884;border-radius:6px;padding:.5rem .8rem;min-width:9rem}}
.card b{{font-size:1.4rem;display:block}}
.na{{color:#b26a00;font-weight:700}}
.sev-error,.ev-P,.ev-I{{}}
.sev-error{{color:#c0322b;font-weight:700}} .sev-warning{{color:#b26a00}} .sev-info{{color:#3273a8}}
.ev{{padding:0 .35rem;border-radius:4px;font-size:.75rem;border:1px solid #8884}}
.ev-S{{background:#ffb02033}} .ev-D{{background:#3273a833}}
footer{{margin-top:1.5rem;color:#888;font-size:.8rem}}
</style></head><body>
<h1>MEES 工程 Dashboard</h1>
<div class="meta">基线提交 <code>{esc(head)}</code>　生成时间 {esc(now)}　来源：check_mees / 追溯生成器 / 指标采集</div>
<div class="banner">⚠ 模拟数据（证据等级 S）：数值来自 MK8 v0.4 试点走查，不代表真实产品质量、过程能力或符合性；N/A = 无充分证据，非 0%。</div>

<h2>1. 概览</h2>
<div class="cards">
<div class="card">检查错误<b class="{'sev-error' if chk['counts']['error'] else ''}">{chk['counts']['error']}</b>{chk['scanned_markdown']} 受控文件</div>
<div class="card">追溯对象/关系<b>{trc['node_count']}/{trc['edge_count']}</b>{trc['counts']['error']} error 诊断</div>
<div class="card">指标 ok/N/A<b>{met['collected']['ok']}/{met['collected']['na']}</b>共 {met['defined']} 定义</div>
<div class="card">证据分布<b>{esc('·'.join(f'{k}:{v}' for k,v in sorted(evid.items())))}</b>无 P/I</div>
</div>

<h2>2. 指标（口径见指标字典 MEES-LIF-013）</h2>
<table><thead><tr><th>标识</th><th>指标</th><th>值</th><th>证据</th><th>说明</th></tr></thead>
<tbody>{metrics_rows}</tbody></table>

<h2>3. 自动检查诊断（check_mees）</h2>
<table><thead><tr><th>严重度</th><th>规则</th><th>位置</th><th>信息</th></tr></thead>
<tbody>{chk_rows}</tbody></table>

<h2>4. 追溯（{esc(trc['source'])}）</h2>
<p class="meta">正向 <code>{esc(q['forward_from'])}</code> → 可达 {len(q['forward_reaches'])} 对象；
反向 <code>{esc(q['reverse_from'])}</code> → 上溯 {len(q['reverse_reaches'])} 对象。</p>
<table><thead><tr><th>严重度</th><th>规则</th><th>对象</th><th>信息</th></tr></thead>
<tbody>{trc_diag_rows}</tbody></table>

<footer>
每个值可回溯：<code>build/check/report.json</code>、<code>build/traceability/traceability.json</code>、<code>build/metrics/metrics.json</code>。
本页由 <code>scripts/generate_dashboard.py</code> 生成，属 Git 忽略的 <code>build/</code>，不作为受控源或发布证据。
</footer>
</body></html>
"""
    out = ROOT / "build" / "dashboard" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"Dashboard：基线 {head}；指标 ok={met['collected']['ok']} na={met['collected']['na']}；"
          f"输出 {out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
