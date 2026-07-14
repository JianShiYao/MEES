# Scripts

用于保存文档检查、追溯矩阵生成、质量指标汇总和发布文档生成脚本。

当前脚本：

- `check_markdown_links.py`：检查 Git 已跟踪和未忽略的新 Markdown 相对链接是否指向存在的文件或目录；本地私有项目、构建输出和其他忽略内容不进入统计。
- `check_template_assets.py`：检查 v0.4 的 18 项模板、13/5 优先级、通用元数据、必要章节、唯一责任和 MK8 九项必须实例。
- `check_mees.py`（v0.5 WP1 P0）：统一检查入口，聚合链接（`LINK-001`）、文档编号唯一（`NUM-001`）、Mermaid 围栏（`MERMAID-001`）、证据状态令牌（`EVID-001`）、导航目标（`NAV-001`）为带规则编号的诊断；输出 `build/check/report.json`。退出码 0 通过 / 1 有 error / 2 工具错误。
- `generate_traceability.py`（v0.5 WP2 P0）：从受控实例（默认 MK8 试点）解析 `derive/trace/verifies` 关系，生成 `build/traceability/traceability.{json,csv,md}`；诊断孤立对象（`TRC-ORPHAN`）、被引用未定义（`TRC-DANGLING`）、无验证技术需求（`TRC-NO-VERIF`，error）和未执行测试（`TRC-TEST-NOTRUN`）。只汇总源关系，不创造缺失关系。
- `collect_metrics.py`（v0.5 WP3 P0）：自动运行上述两个工具并计算首批指标（`MET-DOC/TPL/TRC/VNV-*` 等），输出 `build/metrics/metrics.json`；口径见 [指标字典](../docs/12_Metrics/指标字典.md)。分母为 0、证据仅 `S` 或数据源未接入的指标输出 `N/A`，绝不显示误导性的 0%/100%。
- `generate_dashboard.py`（v0.5 WP4 P0）：运行采集并把 check/追溯/指标 JSON 渲染为自包含静态页 `build/dashboard/index.html`（无服务端/数据库/外部依赖）；显著标注 MK8 模拟证据 `S`，N/A 明确区分于 0%/100%，每个值可回溯到源 JSON。

生成目录 `build/` 已被 Git 忽略。运行方式：

```bash
python scripts/check_markdown_links.py
python scripts/check_template_assets.py
python scripts/check_mees.py
python scripts/generate_traceability.py            # 默认 MK8 试点
python scripts/generate_traceability.py --source <受控实例目录>
```
