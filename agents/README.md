# Agents

用于保存可复用的 AI Agent 协议、提示词、结构化输入输出、样例和测试资产。

v0.6 计划包含 Requirement、Architecture、Review、Test、ASPICE、Metrics 六类 Agent。治理入口见：

- [v0.6 Agent 与 Obsidian 集成建设计划](../docs/00_Introduction/07_v0.6_Agent与Obsidian集成建设计划.md)
- [Agent 协作与治理总览](../docs/16_Agents/00_Agent协作与治理总览.md)
- [Obsidian 与 MCP 接入策略](../docs/17_Tools/Obsidian与MCP接入策略.md)

当前已建立 `schemas/` 三份公共 Schema 和 `protocols/` 六份版本化协议。执行入口为 `scripts/run_agent.py`，BMS 六类走查入口为 `scripts/run_agent_pilot.py`。所有输出固定要求人工复核；不得自动批准门禁、升级证据或发布产品。V6-G2/V6-G5 尚待人工确认，资产不能描述为已批准发布。
