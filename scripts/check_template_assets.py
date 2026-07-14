"""Validate the v0.4 template catalog and MK8 pilot copies."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOT_ROOT = ROOT / "examples" / "mk8-rsiic-v1-v04-pilot"

TEMPLATE_SPECS = {
    "TPL-V04-001": ("00_Governance/Project_Tailoring_Integrated_Plan_Template.md", "P0", "项目经理"),
    "TPL-V04-002": ("00_Governance/Work_Product_Metadata_Baseline_Cover_Template.md", "P0", "配置管理员"),
    "TPL-V04-003": ("10_Engineering/Requirements_Traceability_Template.md", "P0", "系统负责人或软件负责人"),
    "TPL-V04-004": ("10_Engineering/Architecture_Interface_Template.md", "P0", "系统负责人或软件负责人"),
    "TPL-V04-005": ("10_Engineering/Layered_Verification_Plan_Report_Template.md", "P0", "测试负责人"),
    "TPL-V04-006": ("40_Release_Quality/Release_Decision_Archive_Template.md", "P0", "发布负责人"),
    "TPL-V04-007": ("00_Governance/QA_Plan_Nonconformity_Template.md", "P0", "质量负责人"),
    "TPL-V04-008": ("20_Safety/Item_HARA_FSC_Template.md", "P0", "功能安全负责人"),
    "TPL-V04-009": ("20_Safety/Safety_Confirmation_Measures_Template.md", "P0", "功能安全负责人"),
    "TPL-V04-010": ("30_Cybersecurity/Security_Scope_TARA_Template.md", "P0", "网络安全负责人"),
    "TPL-V04-011": ("30_Cybersecurity/Vulnerability_Security_Update_Template.md", "P0", "网络安全负责人"),
    "TPL-V04-012": ("30_Cybersecurity/SBOM_Supplier_Evidence_Template.md", "P0", "配置管理员"),
    "TPL-V04-013": ("20_Safety/EXT_HW_Delivery_Acceptance_Template.md", "P0", "系统负责人"),
    "TPL-V04-014": ("20_Safety/Safety_Analysis_Record_Template.md", "P1", "功能安全负责人"),
    "TPL-V04-015": ("00_Governance/Competence_Authorization_Matrix_Template.md", "P1", "项目经理"),
    "TPL-V04-016": ("00_Governance/Metrics_Quality_Objectives_Template.md", "P1", "质量负责人"),
    "TPL-V04-017": ("00_Governance/CAPA_Process_Improvement_Template.md", "P1", "质量负责人"),
    "TPL-V04-018": ("30_Cybersecurity/Security_Guide_EOL_Notice_Template.md", "P1", "产品负责人"),
}

REQUIRED_METADATA = (
    "模板标识",
    "模板版本",
    "优先级",
    "状态",
    "适用工作产品",
    "最终责任角色",
    "来源差距",
    "证据状态",
)

REQUIRED_SECTIONS = (
    "## 1. 使用说明",
    "## 2. 项目元数据",
    "## 3. 主体内容",
    "## 4. 追溯与变更",
    "## 5. 评审与批准",
    "## 6. 裁剪规则",
    "## 7. 证据与归档",
    "## 8. 版本历史",
)

REQUIRED_PILOT_COPIES = {
    "TPL-V04-001",
    "TPL-V04-002",
    "TPL-V04-003",
    "TPL-V04-004",
    "TPL-V04-005",
    "TPL-V04-006",
    "TPL-V04-007",
    "TPL-V04-012",
    "TPL-V04-013",
}

# v0.5 前瞻草稿模板：单独校验，不计入 v0.4 冻结基线的 18/P0=13/P1=5 计数。
V05_TEMPLATE_SPECS = {
    "TPL-V05-001": ("20_Safety/ESS_Hazard_Analysis_SIL_Determination_Template.md", "P0", "功能安全负责人"),
}


def metadata_value(content: str, label: str) -> str | None:
    match = re.search(rf"^> {re.escape(label)}：(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def main() -> int:
    failures: list[str] = []
    found_ids: set[str] = set()
    priorities = {"P0": 0, "P1": 0}

    for template_id, (relative_path, priority, owner) in TEMPLATE_SPECS.items():
        path = ROOT / "templates" / relative_path
        if not path.exists():
            failures.append(f"missing template: {relative_path}")
            continue

        content = path.read_text(encoding="utf-8")
        for label in REQUIRED_METADATA:
            if metadata_value(content, label) is None:
                failures.append(f"{relative_path}: missing metadata {label}")
        for section in REQUIRED_SECTIONS:
            if section not in content:
                failures.append(f"{relative_path}: missing section {section}")

        actual_id = metadata_value(content, "模板标识")
        if actual_id != template_id:
            failures.append(f"{relative_path}: expected {template_id}, got {actual_id}")
        if actual_id in found_ids:
            failures.append(f"duplicate template id: {actual_id}")
        if actual_id:
            found_ids.add(actual_id)

        actual_priority = metadata_value(content, "优先级")
        actual_owner = metadata_value(content, "最终责任角色")
        if actual_priority != priority:
            failures.append(f"{relative_path}: expected priority {priority}, got {actual_priority}")
        else:
            priorities[priority] += 1
        if actual_owner != owner:
            failures.append(f"{relative_path}: expected owner {owner}, got {actual_owner}")

    v05_found = 0
    for template_id, (relative_path, priority, owner) in V05_TEMPLATE_SPECS.items():
        path = ROOT / "templates" / relative_path
        if not path.exists():
            failures.append(f"missing v0.5 template: {relative_path}")
            continue
        content = path.read_text(encoding="utf-8")
        for label in REQUIRED_METADATA:
            if metadata_value(content, label) is None:
                failures.append(f"{relative_path}: missing metadata {label}")
        for section in REQUIRED_SECTIONS:
            if section not in content:
                failures.append(f"{relative_path}: missing section {section}")
        actual_id = metadata_value(content, "模板标识")
        if actual_id != template_id:
            failures.append(f"{relative_path}: expected {template_id}, got {actual_id}")
        elif actual_id in found_ids:
            failures.append(f"duplicate template id: {actual_id}")
        else:
            found_ids.add(actual_id)
            v05_found += 1

    pilot_ids: set[str] = set()
    if not PILOT_ROOT.exists():
        failures.append(f"missing pilot directory: {PILOT_ROOT.relative_to(ROOT)}")
    else:
        for path in sorted(PILOT_ROOT.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            template_id = metadata_value(content, "模板来源")
            if not template_id:
                continue
            if template_id in pilot_ids:
                failures.append(f"duplicate pilot copy for {template_id}")
            pilot_ids.add(template_id)
            if "[填写：" in content:
                failures.append(f"{path.relative_to(ROOT)}: unresolved template placeholder")

    missing_pilot = sorted(REQUIRED_PILOT_COPIES - pilot_ids)
    if missing_pilot:
        failures.append(f"missing required pilot copies: {', '.join(missing_pilot)}")

    if priorities != {"P0": 13, "P1": 5}:
        failures.append(f"priority counts mismatch: {priorities}")

    if failures:
        print("Template asset validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated 18 templates (P0=13, P1=5), "
        f"{v05_found} v0.5 draft template(s) and "
        f"{len(pilot_ids)} MK8 pilot copies: OK"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
