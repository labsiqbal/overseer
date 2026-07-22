from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[1]
CLI = REPOSITORY / "skill" / "overseer" / "scripts" / "overseer.py"


def run_cli(*arguments: str, expected: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(CLI), *arguments],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != expected:
        raise AssertionError(
            f"Expected exit {expected}, got {completed.returncode}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return json.loads(completed.stdout)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", "utf-8")


def extract_plan(result: dict[str, Any]) -> dict[str, Any]:
    return result["details"]["plan"]


def approval_for(
    plan: dict[str, Any],
    *,
    operation_ids: list[str] | None = None,
    groups: list[str] | None = None,
) -> dict[str, Any]:
    operation_map = {operation["id"]: operation for operation in plan["operations"]}
    selected_ids = operation_ids or [operation["id"] for operation in plan["operations"]]
    selected = [operation_map[identifier] for identifier in selected_ids]
    selected_groups = groups or sorted({operation["group"] for operation in selected})
    displayed_paths = sorted(
        {
            path
            for operation in selected
            for path in (
                [operation["path"]]
                if "path" in operation
                else [operation["source"], operation["destination"]]
            )
        }
    )
    return {
        "protocol": 1,
        "kind": "explicit_owner_confirmation",
        "plan_digest": plan["plan_digest"],
        "snapshot_digest": plan["snapshot_digest"],
        "approved_groups": selected_groups,
        "approved_operation_ids": selected_ids,
        "displayed_paths": displayed_paths,
        "created_at": plan["created_at"],
        "expires_at": plan["expires_at"],
        "host_attestation": {
            "host": "test-host",
            "interaction_ref": "test-explicit-confirmation",
            "statement": "The owner explicitly approved the displayed operations.",
        },
    }


def baseline_model(timestamp: str = "2026-07-22T12:00:00Z") -> dict[str, Any]:
    return {
        "last_material_review": timestamp,
        "last_complete_audit": timestamp,
        "resume_from": "none",
        "canonical_context": [],
        "open_findings": [],
        "history": [{"timestamp": timestamp, "summary": "Initialized Overseer baseline."}],
    }


def inspection_receipt(result: dict[str, Any]) -> dict[str, Any]:
    details = result["details"]
    return {
        "coverage": details["coverage"],
        "snapshot_digest": details["snapshot_digest"],
        "scope": details["scope"],
    }


def initialize_project(project: Path, scratch: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    proposal_path = scratch / "init-proposal.json"
    prepared_path = scratch / "init-prepared.json"
    approval_path = scratch / "init-approval.json"
    write_json(
        proposal_path,
        {
            "ledger_model": baseline_model(),
            "policy": {"protocol": 1, "exact_exclusions": [], "path_classes": {}, "limits": {}},
        },
    )
    prepared = run_cli("init", "prepare", "--root", str(project), "--proposal", str(proposal_path), "--request-id", "init-prepare")
    plan = extract_plan(prepared)
    write_json(prepared_path, prepared)
    write_json(approval_path, approval_for(plan))
    committed = run_cli(
        "init", "commit", "--root", str(project), "--prepared", str(prepared_path), "--approval", str(approval_path), "--request-id", "init-commit"
    )
    return prepared, committed
