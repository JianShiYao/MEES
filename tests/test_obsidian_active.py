"""Obsidian 适配器 read_active（O2 活动笔记）单元测试。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import obsidian_adapter as oa  # noqa: E402


class ReadActive(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = {
            "mode": "O2", "read_roots": ["docs"], "write_roots": ["examples/agent-drafts"],
            "remote_url_env": "TEST_OBS_URL", "remote_token_env": "TEST_OBS_TOKEN",
            "remote_write_enabled": False, "local_write_enabled": False,
            "audit_path": "build/obsidian/audit.jsonl",
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("TEST_OBS_URL", None)
        os.environ.pop("TEST_OBS_TOKEN", None)

    def test_active_reads_via_transport(self):  # 成功：实时连接
        os.environ["TEST_OBS_URL"] = "https://127.0.0.1:27124"
        os.environ["TEST_OBS_TOKEN"] = "secret"
        seen = {}

        def transport(base, relative, headers):
            seen["relative"] = relative
            seen["auth"] = headers.get("Authorization")
            return "# Active Note\n"

        a = oa.ObsidianAdapter(root=self.tmp, config=self.cfg, transport=transport)
        self.assertEqual(a.read_active(), "# Active Note\n")
        self.assertEqual(seen["relative"], "__active__")   # 命中活动笔记端点
        self.assertEqual(seen["auth"], "Bearer secret")

    def test_active_requires_connection(self):  # 无连接：不降级、明确拒绝
        a = oa.ObsidianAdapter(root=self.tmp, config=self.cfg)
        with self.assertRaises(oa.ObsidianAccessError):
            a.read_active()

    def test_audit_records_no_token(self):  # 审计不含 token
        a = oa.ObsidianAdapter(root=self.tmp, config=self.cfg)
        try:
            a.read_active()
        except oa.ObsidianAccessError:
            pass
        audit = (self.tmp / "build/obsidian/audit.jsonl").read_text(encoding="utf-8")
        self.assertIn("O2_ACTIVE", audit)
        self.assertNotIn("secret", audit)


if __name__ == "__main__":
    unittest.main()
