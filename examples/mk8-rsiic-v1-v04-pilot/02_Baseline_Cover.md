# MK8 试点源代码基线封面

> 模板来源：TPL-V04-002
> 实例标识：WP-MK8-BL-001
> 版本：v0.1
> 状态：候选
> 证据状态：P 候选；尚未完成项目配置审计
> 日期：2026-07-14

## 1. 元数据

| 字段 | 内容 |
|---|---|
| 项目/产品 | MK8-P1-MEES-PILOT / MK8-P1 |
| 候选基线 | `BL-MK8-SRC-001` |
| Git 提交 | `7e1d573120d65f6dcba3343481cb3fea3610e5da` |
| 分支 | `feature/software_jingcao_zhu` |
| 检查时状态 | 工作树干净 |
| 配置管理员 | [待确认：项目经理；G1 前；指派配置管理员] |

## 2. 配置项摘要

| CI | 对象 | 观察版本/事实 | 用途 |
|---|---|---|---|
| CI-MK8-PRJ | `.cproject`、`MK8_RSIIC_V1.mex` | NXP MIMXRT1175，Debug/Release/App/Boot0/Boot1 | 构建与硬件配置 |
| CI-MK8-APP | `app/` | 288 个受控文件 | 自研应用和驱动实现 |
| CI-MK8-BMS | `app/application/bms/` | 状态机骨架，多个条件桩 | 试点变更对象 |
| CI-MK8-MDL | `app/application/algorithm/models/` | 14 个模型相关文件 | 算法模型/生成实现 |
| CI-MK8-VER | `app/driver/version/version.h` | `1.1.15+13`，标签 `MK8-P1` | 固件身份 |

## 3. 审计限制

- 未复现 App/Boot0/Boot1 构建。
- 未核对工具、SDK、模型生成和打包工具完整版本。
- 项目 `.gitignore` 排除了 `docs/`、`test/`、工具、DBC 和评审记录。
- 未生成交付包校验和，故本记录不是 G4/G6 正式基线。

## 4. 追溯

本候选基线关联 `CHG-MK8-PILOT-001`、`WP-MK8-REQ-001`、`WP-MK8-ARC-001` 和 `WP-MK8-VER-001`。正式纳入前需配置管理员审计和内容责任人确认。
