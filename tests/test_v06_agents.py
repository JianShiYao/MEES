import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agent_runtime as runtime  # noqa: E402
from obsidian_adapter import ObsidianAccessError, ObsidianAdapter  # noqa: E402


class AgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.original_root = runtime.ROOT
        self.original_protocol_dir = runtime.PROTOCOL_DIR
        runtime.ROOT = self.tmp
        runtime.PROTOCOL_DIR = self.original_protocol_dir
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs/input.md").write_text(
            "SYS-REQ-X-001 SYS-ARC-X-001 IF-X-001 TST-X-001 SYS.2\n- [ ] review\n未执行\n",
            encoding="utf-8",
        )
        (self.tmp / "build").mkdir()
        (self.tmp / "build/metrics.json").write_text(
            json.dumps({"metrics": [{"id": "MET-X", "status": "na"}]}), encoding="utf-8"
        )

    def tearDown(self):
        runtime.ROOT = self.original_root
        runtime.PROTOCOL_DIR = self.original_protocol_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def request(self, agent):
        path = "build/metrics.json" if agent == "metrics" else "docs/input.md"
        return {"run_id": f"test-{agent}", "agent": agent, "task": "test", "inputs": [{"path": path, "evidence_state": "S"}]}

    def test_all_six_protocols_require_human_review(self):
        for agent in ("requirement", "architecture", "review", "test", "aspice", "metrics"):
            with self.subTest(agent=agent):
                result = runtime.run_request(self.request(agent))
                self.assertEqual(result["decision"], "human_review_required")
                self.assertEqual(result["evidence_state"], "S")
                self.assertIn("approve_gate", result["prohibited_actions"])

    def test_rejects_evidence_upgrade_input(self):
        request = self.request("requirement")
        request["inputs"][0]["evidence_state"] = "P"
        with self.assertRaises(runtime.AgentInputError):
            runtime.run_request(request)

    def test_rejects_path_traversal(self):
        request = self.request("requirement")
        request["inputs"][0]["path"] = "docs/../../secret.txt"
        with self.assertRaises(runtime.AgentInputError):
            runtime.run_request(request)


class AgentAssetTests(unittest.TestCase):
    def test_schemas_and_protocols_are_valid_json_contracts(self):
        root = Path(__file__).resolve().parents[1]
        schemas = sorted((root / "agents/schemas").glob("*.json"))
        protocols = sorted((root / "agents/protocols").glob("*.json"))
        self.assertEqual(len(schemas), 3)
        self.assertEqual(len(protocols), 6)
        for path in schemas:
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("$schema", document)
            self.assertEqual(document["type"], "object")
        required = {"id", "version", "human_owner", "allowed_actions", "forbidden_actions", "input_kinds", "output_kind"}
        for path in protocols:
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(required - document.keys())


class ObsidianAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs/note.md").write_text("baseline\n", encoding="utf-8")
        self.config = {
            "read_roots": ["docs"], "write_roots": ["docs/drafts"],
            "remote_url_env": "MEES_TEST_OBSIDIAN_URL",
            "remote_token_env": "MEES_TEST_OBSIDIAN_TOKEN",
            "local_write_enabled": True, "remote_write_enabled": False,
            "audit_path": "build/obsidian/audit.jsonl",
        }
        self.adapter = ObsidianAdapter(self.tmp, self.config)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_o0_read_and_o2_degrade(self):
        self.assertEqual(self.adapter.read_local("docs/note.md"), "baseline\n")
        self.assertEqual(self.adapter.read_remote("docs/note.md"), "baseline\n")

    def test_o3_requires_confirmation_and_rolls_back(self):
        target = self.tmp / "docs/drafts/proposal.md"
        proposal = self.adapter.propose_write("docs/drafts/proposal.md", "draft\n")
        with self.assertRaises(ObsidianAccessError):
            self.adapter.apply_write(proposal, "wrong")
        rollback = self.adapter.apply_write(proposal, proposal["proposal_id"])
        self.assertEqual(target.read_text(encoding="utf-8"), "draft\n")
        self.adapter.rollback(rollback.relative_to(self.tmp).as_posix())
        self.assertFalse(target.exists())

    def test_write_outside_allowlist_is_rejected(self):
        with self.assertRaises(ObsidianAccessError):
            self.adapter.propose_write("docs/note.md", "changed\n")

    def test_o2_rejects_path_traversal_before_transport(self):
        with self.assertRaises(ObsidianAccessError):
            self.adapter.read_remote("docs/../../secret.md")
