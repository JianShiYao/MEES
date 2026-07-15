"""MEES v0.5 自动化脚本单元测试（WP7/F1）。

覆盖类：成功、规则失败、无数据、格式错误、断链。
标准库 unittest，无外部依赖。运行：python -m unittest discover -s tests
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_mees as cm  # noqa: E402
import check_template_assets as cta  # noqa: E402
import generate_traceability as gt  # noqa: E402
import collect_metrics as cmet  # noqa: E402


class CheckMeesRules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._root = cm.ROOT
        cm.ROOT = self.tmp

    def tearDown(self):
        cm.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def w(self, rel, text):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_links_success(self):
        a = self.w("docs/a.md", "[x](b.md)")
        self.w("docs/b.md", "# b")
        self.assertEqual(cm.rule_links([a]), [])

    def test_links_broken(self):  # 断链
        a = self.w("docs/a.md", "[x](missing.md)")
        d = cm.rule_links([a])
        self.assertTrue(any(x["rule_id"] == "LINK-001" for x in d))

    def test_docnum_duplicate(self):  # 规则失败
        a = self.w("docs/a.md", "> 文档编号：MEES-PRO-999\n")
        b = self.w("docs/b.md", "> 文档编号：MEES-PRO-999\n")
        d = cm.rule_docnum([a, b])
        self.assertTrue(any(x["rule_id"] == "NUM-001" for x in d))

    def test_fence_unbalanced(self):  # 格式错误
        a = self.w("docs/a.md", "```mermaid\nflowchart LR\nA-->B\n")
        d = cm.rule_fences([a])
        self.assertTrue(any(x["rule_id"] == "FENCE-001" for x in d))

    def test_evidence_bad_token(self):
        a = self.w("docs/a.md", "证据状态：X\n")
        d = cm.rule_evidence([a])
        self.assertTrue(any(x["rule_id"] == "EVID-001" for x in d))

    def test_docs_scope_outside(self):  # LINK-002 站点外链接
        a = self.w("docs/a.md", "[x](../outside.md)")
        self.w("outside.md", "# out")
        d = cm.rule_docs_scope([a])
        self.assertTrue(any(x["rule_id"] == "LINK-002" for x in d))

    def test_nav_missing_target(self):
        (self.tmp / "docs").mkdir(parents=True, exist_ok=True)
        (self.tmp / "mkdocs.yml").write_text("nav:\n  - A: a.md\n", encoding="utf-8")
        d = cm.rule_nav([])
        self.assertTrue(any(x["rule_id"] == "NAV-001" for x in d))

    def test_candidate_lifecycle_mismatch(self):
        self.w(
            "docs/candidate.md",
            "> 版本：v0.5.0-dev\n> 状态：评审中\n> 最后更新：2026-07-15\n",
        )
        original = cm.V051_CANDIDATE_DOCS
        cm.V051_CANDIDATE_DOCS = ("docs/candidate.md",)
        try:
            d = cm.rule_baseline_lifecycle([])
        finally:
            cm.V051_CANDIDATE_DOCS = original
        self.assertEqual(
            len([x for x in d if x["rule_id"] == "BASELINE-001"]),
            2,
        )


class Traceability(unittest.TestCase):
    def test_extract_ids_numeric_siblings(self):
        self.assertEqual(gt.extract_ids("TST-MK8-001/002/003"),
                         ["TST-MK8-001", "TST-MK8-002", "TST-MK8-003"])

    def test_extract_ids_distinct_prefixes(self):
        self.assertEqual(gt.extract_ids("SYS-ARC-MK8-001/IF-MK8-FAULT-001"),
                         ["SYS-ARC-MK8-001", "IF-MK8-FAULT-001"])

    def test_parse_tables(self):  # 格式解析
        t = "| 标识 | 来源/理由 |\n|---|---|\n| SYS-REQ-X-001 | PRD-X-001 |\n"
        tables = gt.parse_tables(t)
        self.assertEqual(len(tables), 1)
        header, rows = tables[0]
        self.assertIn("标识", header[0])
        self.assertEqual(len(rows), 1)

    def _model(self, text):
        src = Path(tempfile.mkdtemp())
        (src / "x.md").write_text(text, encoding="utf-8")
        try:
            return gt.diagnose(*gt.build_model(src))
        finally:
            shutil.rmtree(src, ignore_errors=True)

    def test_no_verification_error(self):  # 无数据/规则失败
        d = self._model("| 标识 | 层级 | 来源/理由 |\n|---|---|---|\n"
                        "| SYS-REQ-Z-900 | 系统需求 | PRD-Z-001 |\n")
        self.assertTrue(any(x["rule_id"] == "TRC-NO-VERIF" and x["severity"] == "error" for x in d))

    def test_test_notrun(self):
        d = self._model("| TST | 追溯 | 状态 |\n|---|---|---|\n"
                        "| TST-Z-001 | SYS-REQ-Z-900 | 未执行 |\n")
        self.assertTrue(any(x["rule_id"] == "TRC-TEST-NOTRUN" for x in d))

    def test_verified_requirement_no_error(self):  # 成功：需求被验证
        d = self._model("| TST | 追溯 | 状态 |\n|---|---|---|\n"
                        "| TST-Z-001 | SYS-REQ-Z-900 | 已执行 |\n")
        self.assertFalse(any(x["rule_id"] == "TRC-NO-VERIF" for x in d))


class Metrics(unittest.TestCase):
    def test_pct_normal(self):
        self.assertEqual(cmet.pct(1, 2), 50.0)

    def test_pct_zero_denominator(self):  # 无数据 → None（不虚假绿灯）
        self.assertIsNone(cmet.pct(0, 0))

    def test_pct_full(self):
        self.assertEqual(cmet.pct(3, 3), 100.0)


class TemplateLifecycle(unittest.TestCase):
    def test_expected_lifecycle(self):
        content = "> 模板版本：v0.5.1-dev\n> 状态：评审中（v0.5.1 收口候选）\n"
        self.assertEqual(
            cta.validate_lifecycle(
                content,
                "template.md",
                "v0.5.1-dev",
                "评审中（v0.5.1 收口候选）",
            ),
            [],
        )

    def test_rejects_draft_in_correction_candidate(self):
        content = "> 模板版本：v0.5.0-dev\n> 状态：草稿\n"
        failures = cta.validate_lifecycle(
            content,
            "template.md",
            "v0.5.1-dev",
            "评审中（v0.5.1 收口候选）",
        )
        self.assertEqual(len(failures), 2)


if __name__ == "__main__":
    unittest.main()
