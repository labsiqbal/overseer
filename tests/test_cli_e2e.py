from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import approval_for, baseline_model, extract_plan, initialize_project, inspection_receipt, run_cli, write_json


class OverseerCliE2E(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.scratch = self.base / "scratch"
        self.project.mkdir()
        self.scratch.mkdir()
        (self.project / "README.md").write_text("# Example\n\nCurrent report: downloads/report-v2.pdf\n", "utf-8")
        (self.project / "downloads").mkdir()
        (self.project / "downloads" / "report-v2.pdf").write_bytes(b"report-v2\n")

    def test_first_scan_is_read_only_then_initialization_commits(self) -> None:
        before = sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*"))
        scan = run_cli("scan", "--root", str(self.project), "--session-path", "README.md", "--request-id", "first-scan")
        self.assertEqual(scan["kind"], "baseline_required")
        self.assertFalse(scan["details"]["initialized"])
        after = sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*"))
        self.assertEqual(before, after)

        _, committed = initialize_project(self.project, self.scratch)
        self.assertEqual(committed["status"], "ok")
        self.assertEqual(committed["details"]["status"], "committed")
        self.assertTrue((self.project / "overseer.md").is_file())
        self.assertTrue((self.project / "overseer" / "state.json").is_file())
        self.assertTrue((self.project / "overseer" / "policy.json").is_file())
        self.assertFalse(any((self.project / "overseer" / "transactions").glob("*/preimages")))
        state_text = (self.project / "overseer" / "state.json").read_text("utf-8")
        self.assertNotIn(str(self.project), state_text)

        scan = run_cli("scan", "--root", str(self.project), "--session-path", "README.md", "--request-id", "after-init")
        self.assertEqual(scan["kind"], "inspection")
        self.assertTrue(scan["details"]["initialized"])

    def test_repeat_ledger_model_is_true_noop(self) -> None:
        initialize_project(self.project, self.scratch)
        scan = run_cli("scan", "--root", str(self.project), "--session-path", "README.md", "--request-id", "scan-noop")
        transaction_root = self.project / "overseer" / "transactions"
        before_transactions = sorted(path.name for path in transaction_root.iterdir())
        proposal = {
            "source_inspection": inspection_receipt(scan),
            "ledger_model": baseline_model(),
            "reason": "No material context change",
        }
        proposal_path = self.scratch / "ledger-noop.json"
        write_json(proposal_path, proposal)
        result = run_cli("ledger", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "ledger-noop")
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(before_transactions, sorted(path.name for path in transaction_root.iterdir()))

    def test_clean_repairs_reference_then_moves_exact_file(self) -> None:
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-before-clean")
        proposal = {
            "source_inspection": inspection_receipt(audit),
            "intents": [
                {
                    "id": "repair-readme",
                    "kind": "edit_document",
                    "group": "Documentation",
                    "path": "README.md",
                    "content": "# Example\n\nCurrent report: reports/current-report.pdf\n",
                    "reason": "Repair the owner-confirmed canonical report reference",
                },
                {
                    "id": "move-report",
                    "kind": "move",
                    "group": "Organize",
                    "source": "downloads/report-v2.pdf",
                    "destination": "reports/current-report.pdf",
                    "depends_on": ["repair-readme"],
                    "reason": "Give the current report a canonical path",
                },
            ],
        }
        prepared_path = self.scratch / "clean-prepared.json"
        proposal_path = self.scratch / "clean-proposal.json"
        approval_path = self.scratch / "clean-approval.json"
        write_json(proposal_path, proposal)
        prepared = run_cli("clean", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "clean-prepare")
        plan = extract_plan(prepared)
        move = next(operation for operation in plan["operations"] if operation["id"] == "move-report")
        self.assertIn("repair-readme", move["dependencies"])
        write_json(prepared_path, prepared)
        write_json(approval_path, approval_for(plan))
        result = run_cli("clean", "commit", "--root", str(self.project), "--prepared", str(prepared_path), "--approval", str(approval_path), "--request-id", "clean-commit")
        self.assertEqual(result["details"]["status"], "committed")
        self.assertFalse((self.project / "downloads" / "report-v2.pdf").exists())
        self.assertEqual((self.project / "reports" / "current-report.pdf").read_bytes(), b"report-v2\n")
        self.assertIn("reports/current-report.pdf", (self.project / "README.md").read_text("utf-8"))

    def test_dependency_closed_approval_is_enforced(self) -> None:
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-dependency")
        proposal_path = self.scratch / "dependency-proposal.json"
        prepared_path = self.scratch / "dependency-prepared.json"
        approval_path = self.scratch / "dependency-approval.json"
        write_json(
            proposal_path,
            {
                "source_inspection": inspection_receipt(audit),
                "intents": [
                    {"id":"repair","kind":"edit_document","group":"Documentation","path":"README.md","content":"# Example\n\nCurrent report: reports/current.pdf\n","reason":"Repair reference"},
                    {"id":"move","kind":"move","group":"Organize","source":"downloads/report-v2.pdf","destination":"reports/current.pdf","depends_on":["repair"],"reason":"Canonical move"}
                ]
            },
        )
        prepared = run_cli("clean", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "dependency-prepare")
        plan = extract_plan(prepared)
        write_json(prepared_path, prepared)
        write_json(approval_path, approval_for(plan, operation_ids=["move"], groups=["Organize"]))
        result = run_cli("clean", "commit", "--root", str(self.project), "--prepared", str(prepared_path), "--approval", str(approval_path), "--request-id", "dependency-commit", expected=2)
        self.assertEqual(result["details"]["code"], "UNAPPROVED_DEPENDENCY")
        self.assertTrue((self.project / "downloads" / "report-v2.pdf").exists())

    def test_archive_preserves_original_path_and_manifest(self) -> None:
        (self.project / "loose.csv").write_text("a,b\n1,2\n", "utf-8")
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-archive")
        proposal_path = self.scratch / "archive-proposal.json"
        prepared_path = self.scratch / "archive-prepared.json"
        approval_path = self.scratch / "archive-approval.json"
        write_json(
            proposal_path,
            {
                "source_inspection": inspection_receipt(audit),
                "intents": [{"id":"archive-loose","kind":"archive","group":"Archive","source":"loose.csv","canonical_replacement":"reports/current.csv","reason":"Archive owner-confirmed superseded export"}],
            },
        )
        prepared = run_cli("clean", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "archive-prepare")
        plan = extract_plan(prepared)
        archive = plan["operations"][0]
        self.assertTrue(archive["destination"].endswith(f"/{plan['transaction_id']}/loose.csv"))
        write_json(prepared_path, prepared)
        write_json(approval_path, approval_for(plan))
        run_cli("clean", "commit", "--root", str(self.project), "--prepared", str(prepared_path), "--approval", str(approval_path), "--request-id", "archive-commit")
        self.assertFalse((self.project / "loose.csv").exists())
        archived = self.project.joinpath(*archive["destination"].split("/"))
        self.assertEqual(archived.read_text("utf-8"), "a,b\n1,2\n")
        manifest = self.project.joinpath(*archive["destination"].split("/")[:4], "manifest.json")
        value = json.loads(manifest.read_text("utf-8"))
        self.assertEqual(value["entries"][0]["original_path"], "loose.csv")

    def test_secret_evidence_is_redacted(self) -> None:
        (self.project / ".env").write_text("TOKEN=do-not-expose\n", "utf-8")
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-secret")
        serialized = json.dumps(audit)
        self.assertNotIn("do-not-expose", serialized)
        self.assertNotIn('"path": ".env"', serialized)
        secret = next(record for record in audit["details"]["records"] if record["classification"]["secret"])
        self.assertIsNone(secret["path"])
        self.assertIn("path_digest", secret)

    def test_git_evidence_redacts_secret_paths(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.project)], check=True, capture_output=True)
        (self.project / ".env").write_text("TOKEN=hidden\n", "utf-8")
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-git-secret")
        self.assertTrue(audit["details"]["git"]["available"])
        serialized = json.dumps(audit["details"]["git"])
        self.assertNotIn(".env", serialized)
        self.assertNotIn("hidden", json.dumps(audit))
        self.assertIn("secret-path", serialized)

    def test_source_code_move_and_symlink_escape_fail_closed(self) -> None:
        (self.project / "app.py").write_text("print('safe')\n", "utf-8")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "value.txt").write_text("outside\n", "utf-8")
        os.symlink(outside, self.project / "escape")
        os.symlink(outside / "value.txt", self.project / "external-link")
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-protected")
        for index, intent in enumerate(
            [
                {"id":"move-source","kind":"move","group":"Organize","source":"app.py","destination":"old/app.py","reason":"Should be blocked"},
                {"id":"escape-edit","kind":"edit_document","group":"Documentation","path":"escape/value.txt","content":"bad\n","reason":"Should be blocked"},
                {"id":"move-external-link","kind":"move","group":"Organize","source":"external-link","destination":"organized/external-link","reason":"External symlink should be blocked"},
            ]
        ):
            proposal_path = self.scratch / f"protected-{index}.json"
            write_json(
                proposal_path,
                {"source_inspection":inspection_receipt(audit),"intents":[intent]},
            )
            result = run_cli("clean", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", f"protected-{index}", expected=2)
            self.assertIn(result["details"]["code"], {"PROTECTED_PATH", "ROOT_ESCAPE", "UNSUPPORTED_OBJECT"})
        self.assertEqual((outside / "value.txt").read_text("utf-8"), "outside\n")
        self.assertTrue((self.project / "external-link").is_symlink())

    def test_forged_or_stale_inspection_receipt_cannot_prepare(self) -> None:
        initialize_project(self.project, self.scratch)
        proposal_path = self.scratch / "forged-inspection.json"
        write_json(
            proposal_path,
            {
                "source_inspection": {"coverage":"complete","snapshot_digest":"0" * 64,"scope":{"mode":"audit"}},
                "intents": [{"id":"edit","kind":"edit_document","group":"Documentation","path":"README.md","content":"# Forged\n","reason":"Must not apply"}],
            },
        )
        result = run_cli("clean", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "forged-inspection", expected=2)
        self.assertEqual(result["details"]["code"], "STALE_SNAPSHOT")
        self.assertIn("Current report", (self.project / "README.md").read_text("utf-8"))

    def test_policy_change_is_isolated_and_takes_effect_after_rescan(self) -> None:
        (self.project / "ignored.txt").write_text("ignore me\n", "utf-8")
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-policy")
        proposal_path = self.scratch / "policy-proposal.json"
        prepared_path = self.scratch / "policy-prepared.json"
        approval_path = self.scratch / "policy-approval.json"
        write_json(
            proposal_path,
            {
                "source_inspection": inspection_receipt(audit),
                "intents": [{
                    "id":"policy-exclusion",
                    "kind":"write_policy",
                    "group":"Documentation",
                    "policy":{"protocol":1,"exact_exclusions":["ignored.txt"],"path_classes":{},"limits":{}},
                    "reason":"Owner approved this exact audit exclusion"
                }],
            },
        )
        prepared = run_cli("clean", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "policy-prepare")
        plan = extract_plan(prepared)
        self.assertEqual([operation["primitive"] for operation in plan["operations"]], ["WritePolicy"])
        write_json(prepared_path, prepared)
        write_json(approval_path, approval_for(plan))
        run_cli("clean", "commit", "--root", str(self.project), "--prepared", str(prepared_path), "--approval", str(approval_path), "--request-id", "policy-commit")
        after = run_cli("audit", "--root", str(self.project), "--request-id", "audit-policy-after")
        paths = {record["path"] for record in after["details"]["records"] if record.get("path")}
        self.assertNotIn("ignored.txt", paths)

    def test_approval_displayed_paths_are_exact(self) -> None:
        initialize_project(self.project, self.scratch)
        audit = run_cli("audit", "--root", str(self.project), "--request-id", "audit-path-approval")
        proposal_path = self.scratch / "approval-path-proposal.json"
        prepared_path = self.scratch / "approval-path-prepared.json"
        approval_path = self.scratch / "approval-path-approval.json"
        write_json(
            proposal_path,
            {
                "source_inspection": inspection_receipt(audit),
                "intents": [{"id":"edit-readme","kind":"edit_document","group":"Documentation","path":"README.md","content":"# Changed\n","reason":"Approved exact edit"}],
            },
        )
        prepared = run_cli("clean", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "approval-path-prepare")
        plan = extract_plan(prepared)
        approval = approval_for(plan)
        approval["displayed_paths"] = ["OTHER.md"]
        write_json(prepared_path, prepared)
        write_json(approval_path, approval)
        result = run_cli("clean", "commit", "--root", str(self.project), "--prepared", str(prepared_path), "--approval", str(approval_path), "--request-id", "approval-path-commit", expected=2)
        self.assertEqual(result["details"]["code"], "APPROVAL_REQUIRED")
        self.assertIn("Current report", (self.project / "README.md").read_text("utf-8"))

    def test_existing_overseer_namespace_blocks_initialization(self) -> None:
        (self.project / "overseer.md").write_text("Unrelated owner file\n", "utf-8")
        scan = run_cli("scan", "--root", str(self.project), "--session-path", "README.md", "--request-id", "collision-scan")
        self.assertIn("overseer.md", scan["details"]["collisions"])
        proposal_path = self.scratch / "collision-init.json"
        write_json(proposal_path, {"ledger_model": baseline_model()})
        result = run_cli("init", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "collision-init", expected=2)
        self.assertEqual(result["details"]["code"], "ALREADY_INITIALIZED")
        self.assertEqual((self.project / "overseer.md").read_text("utf-8"), "Unrelated owner file\n")

    def test_existing_overseer_directory_blocks_initialization(self) -> None:
        namespace = self.project / "overseer"
        namespace.mkdir()
        sentinel = namespace / "owner-file.txt"
        sentinel.write_text("Owner data\n", "utf-8")
        scan = run_cli("scan", "--root", str(self.project), "--request-id", "directory-collision-scan")
        self.assertIn("overseer/", scan["details"]["collisions"])
        proposal_path = self.scratch / "directory-collision-init.json"
        write_json(proposal_path, {"ledger_model": baseline_model()})
        result = run_cli("init", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "directory-collision-init", expected=2)
        self.assertEqual(result["details"]["code"], "ALREADY_INITIALIZED")
        self.assertEqual(sentinel.read_text("utf-8"), "Owner data\n")

    def test_namespace_race_blocks_initialization_commit(self) -> None:
        proposal_path = self.scratch / "race-init.json"
        write_json(proposal_path, {"ledger_model": baseline_model()})
        prepared = run_cli("init", "prepare", "--root", str(self.project), "--proposal", str(proposal_path), "--request-id", "race-prepare")
        plan = extract_plan(prepared)
        prepared_path = self.scratch / "race-prepared.json"
        approval_path = self.scratch / "race-approval.json"
        write_json(prepared_path, prepared)
        write_json(approval_path, approval_for(plan))
        namespace = self.project / "overseer"
        namespace.mkdir()
        sentinel = namespace / "owner-file.txt"
        sentinel.write_text("Owner data\n", "utf-8")
        result = run_cli("init", "commit", "--root", str(self.project), "--prepared", str(prepared_path), "--approval", str(approval_path), "--request-id", "race-commit", expected=2)
        self.assertEqual(result["details"]["code"], "ALREADY_INITIALIZED")
        self.assertEqual(sentinel.read_text("utf-8"), "Owner data\n")
        self.assertFalse((self.project / "overseer.md").exists())


if __name__ == "__main__":
    unittest.main()
