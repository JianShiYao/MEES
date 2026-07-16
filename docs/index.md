# MEES 首页

欢迎进入 **MEES — 现代嵌入式研发工程体系**。

## 使用路径

- 管理者：先阅读 [MEES 总览](00_Introduction/00_MEES总览.md)、[v0.2 核心过程总览](01_Main_Process/00_核心过程总览.md)和[建设路线图](00_Introduction/01_建设路线图.md)。
- 过程维护者：使用[文档与编号规范](00_Introduction/02_文档与编号规范.md)和[版本规范](00_Introduction/03_版本规范.md)管理编号、状态、候选提交和发布标签；证据等级与产品/能力边界以[边界与证据声明](00_Introduction/09_边界与证据声明.md)为准。
- 产品负责人：阅读[产品规划过程](01_Product_Management/01_产品规划过程.md)，建立产品目标、需求组合、路线图和 G0 决策。
- BMS 试点参与者：从[MK8 RSIIC V1 项目试点](15_Case_Study/MK8_RSIIC_V1项目试点.md)开始，按[证据台账](15_Case_Study/MK8_RSIIC_V1证据台账.md)恢复项目证据，并用[v0.4 模板走查](15_Case_Study/MK8_RSIIC_V1_v0.4模板走查.md)理解当前模拟实例与产品 `No-Go` 边界。
- 项目经理：阅读[项目管理过程](01_Main_Process/01_项目管理过程.md)和[项目管理过程检查表](14_Checklists/项目管理过程检查表.md)。
- 系统工程师：阅读[需求管理过程](01_Main_Process/02_需求管理过程.md)、[架构设计过程](01_Main_Process/03_架构设计过程.md)和[系统工程过程](03_System_Engineering/01_系统工程过程.md)。
- 软件工程师：阅读[软件工程过程](04_Software_Engineering/01_软件工程过程.md)，落实软件需求、架构、详细设计、实现与单元验证。
- 测试工程师：阅读[验证确认过程](01_Main_Process/04_验证确认过程.md)、[集成与测试过程](05_Test_Engineering/01_集成与测试过程.md)和[验证确认过程检查表](14_Checklists/验证确认过程检查表.md)。
- 质量人员：阅读 [ASPICE + ISO/IEC 33020 详细映射](11_Process_Management/ASPICE_ISO_IEC_33020过程映射表.md)、[ISO/IEC 33020 中文工程解读](11_Process_Management/ISO_IEC_33020中文工程解读.md)、审核、[配置管理过程](01_Main_Process/06_配置管理过程.md) 和度量。
- 功能安全人员：阅读 [ISO 26262 过程映射](07_Functional_Safety/ISO_26262过程映射.md)，复核安全生命周期、`EXT-HW` 和确认措施接口。
- 网络安全人员：阅读 [IEC 62443 过程映射](08_Cybersecurity/IEC_62443过程映射.md)，复核 TARA、漏洞、补丁和退役接口。
- 配置与发布负责人：阅读[配置管理过程](01_Main_Process/06_配置管理过程.md)、[变更与问题管理过程](01_Main_Process/07_变更与问题管理过程.md)和[发布管理过程](01_Main_Process/05_发布管理过程.md)。
- Agent/工具维护者：从 [v0.6 建设计划](00_Introduction/07_v0.6_Agent与Obsidian集成建设计划.md)、[Agent 协作与治理总览](16_Agents/00_Agent协作与治理总览.md)和[Obsidian 与 MCP 接入策略](17_Tools/Obsidian与MCP接入策略.md)开始。

## 当前建设重点

当前阶段为 **v1.0 内部整合基线**（v0.6.0 已发布）。

1. 阅读 [v1.0 内部整合基线建设计划](00_Introduction/08_v1.0内部整合基线建设计划.md)，了解整合目标、WP0–WP6、V1 门禁与退出判据。
2. 用 [评审与走查索引](11_Process_Management/评审与走查索引.md) 定位历次门禁决定与走查证据。
3. 使用 `python scripts/run_all_checks.py --allow-npx` 复现统一检查、追溯、Agent 案例、Mermaid 和 MkDocs 结果。
4. 边界不变：Agent 输出均需人工决定，产品保持 `No-Go`；Obsidian 真实 O2 只读与受控本地写入已试点（V6-G3/G4 已签），REST 写入 Obsidian 为后续能力。
