from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import approval_for, extract_plan, initialize_project, inspection_receipt, run_cli


CORE_PATH = Path(__file__).resolve().parents[1] / "skill" / "overseer" / "scripts"
sys.path.insert(0, str(CORE_PATH))

from overseer_core.engine import run  # noqa: E402
from overseer_core.paths import open_root  # noqa: E402
from overseer_core.transactions import apply_plan  # noqa: E402
import overseer_core.transactions as transactions  # noqa: E402


class TransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.scratch = self.base / "scratch"
        self.project.mkdir()
        self.scratch.mkdir()
        (self.project / "README.md").write_text("# Before\n", "utf-8")
        (self.project / "notes.md").write_text("Before notes\n", "utf-8")
        initialize_project(self.project, self.scratch)

    def _two_edit_plan(self) -> tuple[dict, dict]:
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-two-edits")
        proposal = {
            "protocol": 1,
            "request_id": "prepare-two-edits",
            "kind": "prepare_clean",
            "root": str(self.project),
            "source_inspection": inspection_receipt(audit),
            "intents": [
                {"id":"edit-readme","kind":"edit_document","group":"Documentation","path":"README.md","content":"# After\n","reason":"Update heading"},
                {"id":"edit-notes","kind":"edit_document","group":"Documentation","path":"notes.md","content":"After notes\n","reason":"Update notes"},
            ],
        }
        prepared = run(proposal)
        plan = extract_plan(prepared)
        return plan, approval_for(plan)

    def test_stale_before_hash_rejects_without_overwrite(self) -> None:
        plan, approval = self._two_edit_plan()
        (self.project / "README.md").write_text("External edit\n", "utf-8")
        result = run({"protocol":1,"request_id":"stale-commit","kind":"commit","root":str(self.project),"plan":plan,"approval":approval})
        self.assertEqual(result["details"]["code"], "STALE_SNAPSHOT")
        self.assertEqual((self.project / "README.md").read_text("utf-8"), "External edit\n")
        self.assertEqual((self.project / "notes.md").read_text("utf-8"), "Before notes\n")

    def test_failure_after_first_write_restores_exact_preimage(self) -> None:
        plan, approval = self._two_edit_plan()
        real_apply = transactions._apply_operation
        calls = 0

        def fail_second(root, transaction_dir, operation):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected failure")
            return real_apply(root, transaction_dir, operation)

        with patch.object(transactions, "_apply_operation", side_effect=fail_second):
            with self.assertRaises(Exception):
                apply_plan(open_root(str(self.project)), plan, approval)
        self.assertEqual((self.project / "README.md").read_text("utf-8"), "# Before\n")
        self.assertEqual((self.project / "notes.md").read_text("utf-8"), "Before notes\n")
        journals = list((self.project / "overseer" / "transactions").glob("*/journal.json"))
        states = [json.loads(path.read_text("utf-8"))["state"] for path in journals]
        self.assertIn("rolled_back", states)

    def test_explicit_recovery_rolls_back_interrupted_journal(self) -> None:
        plan, approval = self._two_edit_plan()
        operation = next(item for item in plan["operations"] if item["id"] == "edit-readme")
        transaction_dir = self.project / "overseer" / "transactions" / plan["transaction_id"]
        preimages = transaction_dir / "preimages"
        staged = transaction_dir / "staged"
        preimages.mkdir(parents=True)
        staged.mkdir()
        original = (self.project / "README.md").read_bytes()
        (preimages / "edit-readme.bin").write_bytes(original)
        (self.project / "README.md").write_bytes(base64.b64decode(operation["content_b64"]))
        journal = {
            "protocol": 1,
            "transaction_id": plan["transaction_id"],
            "state": "applying",
            "plan": plan,
            "approval_digest": "interrupted-test",
            "selected_operation_ids": [item["id"] for item in plan["operations"]],
            "applied_operation_ids": ["edit-readme"],
            "current_operation_id": None,
            "state_created": False,
            "manifest_paths": [],
            "started_at": plan["created_at"],
            "finished_at": None,
            "error": "simulated process interruption",
        }
        (transaction_dir / "journal.json").write_text(json.dumps(journal), "utf-8")
        result = run_cli(
            "recover", "rollback", "--root", str(self.project), "--transaction", plan["transaction_id"], "--request-id", "recover-interrupted"
        )
        self.assertEqual(result["details"]["status"], "rolled_back")
        self.assertEqual((self.project / "README.md").read_bytes(), original)
        self.assertEqual((self.project / "notes.md").read_text("utf-8"), "Before notes\n")

    def test_explicit_recovery_verifies_fully_applied_journal(self) -> None:
        plan, approval = self._two_edit_plan()
        transaction_dir = self.project / "overseer" / "transactions" / plan["transaction_id"]
        preimages = transaction_dir / "preimages"
        staged = transaction_dir / "staged"
        preimages.mkdir(parents=True)
        staged.mkdir()
        for operation in plan["operations"]:
            path = self.project / operation["path"]
            (preimages / f"{operation['id']}.bin").write_bytes(path.read_bytes())
            path.write_bytes(base64.b64decode(operation["content_b64"]))
        journal = {
            "protocol": 1,
            "transaction_id": plan["transaction_id"],
            "state": "applying",
            "plan": plan,
            "approval_digest": "interrupted-test",
            "selected_operation_ids": [item["id"] for item in plan["operations"]],
            "applied_operation_ids": [item["id"] for item in plan["operations"]],
            "current_operation_id": None,
            "state_created": False,
            "manifest_paths": [],
            "started_at": plan["created_at"],
            "finished_at": None,
            "error": "simulated process interruption after apply",
        }
        (transaction_dir / "journal.json").write_text(json.dumps(journal), "utf-8")
        result = run_cli(
            "recover", "verify", "--root", str(self.project), "--transaction", plan["transaction_id"], "--request-id", "verify-interrupted"
        )
        self.assertEqual(result["details"]["status"], "committed")
        self.assertEqual((self.project / "README.md").read_text("utf-8"), "# After\n")
        self.assertEqual((self.project / "notes.md").read_text("utf-8"), "After notes\n")
        self.assertFalse(preimages.exists())


if __name__ == "__main__":
    unittest.main()
