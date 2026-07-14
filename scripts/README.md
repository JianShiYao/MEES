# Scripts

用于保存文档检查、追溯矩阵生成、质量指标汇总和发布文档生成脚本。

当前脚本：

- `check_markdown_links.py`：检查 Git 已跟踪和未忽略的新 Markdown 相对链接是否指向存在的文件或目录；本地私有项目、构建输出和其他忽略内容不进入统计。
- `check_template_assets.py`：检查 v0.4 的 18 项模板、13/5 优先级、通用元数据、必要章节、唯一责任和 MK8 九项必须实例。

运行方式：

```bash
python scripts/check_markdown_links.py
python scripts/check_template_assets.py
```
