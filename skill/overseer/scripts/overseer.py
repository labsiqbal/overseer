#!/usr/bin/env python3
"""Structured, non-interactive command-line adapter for Overseer."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from overseer_core import run
from overseer_core.common import canonical_json


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        request = _request(args)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "protocol": 1,
            "request_id": getattr(args, "request_id", None) or "cli-invalid",
            "kind": "failure",
            "status": "error",
            "details": {
                "code": "INVALID_REQUEST",
                "message": str(exc),
                "stage": "cli",
                "retryable": False,
                "recovery_status": "none",
            },
        }
        print(canonical_json(result))
        return 2
    result = run(request)
    print(canonical_json(result))
    if result["kind"] != "failure":
        return 0
    code = result["details"]["code"]
    if code in {"RECOVERY_REQUIRED", "ROLLBACK_CONFLICT", "VERIFY_FAILED"}:
        return 3
    if code in {"IO_ERROR", "BUSY"}:
        return 4
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="overseer", description="Deterministic project context hygiene helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute a complete protocol request")
    run_parser.add_argument("--request", required=True, help="JSON file or - for stdin")

    for mode in ("scan", "audit", "capability"):
        child = subparsers.add_parser(mode)
        _common(child)
        if mode == "scan":
            child.add_argument("--session-path", action="append", default=[])
            child.add_argument("--referenced-path", action="append", default=[])

    init = subparsers.add_parser("init")
    init_sub = init.add_subparsers(dest="action", required=True)
    init_prepare = init_sub.add_parser("prepare")
    _common(init_prepare)
    init_prepare.add_argument("--proposal", required=True)
    init_commit = init_sub.add_parser("commit")
    _commit_args(init_commit)

    ledger = subparsers.add_parser("ledger")
    ledger_sub = ledger.add_subparsers(dest="action", required=True)
    ledger_prepare = ledger_sub.add_parser("prepare")
    _common(ledger_prepare)
    ledger_prepare.add_argument("--proposal", required=True)
    ledger_commit = ledger_sub.add_parser("commit")
    _commit_args(ledger_commit)

    clean = subparsers.add_parser("clean")
    clean_sub = clean.add_subparsers(dest="action", required=True)
    clean_prepare = clean_sub.add_parser("prepare")
    _common(clean_prepare)
    clean_prepare.add_argument("--proposal", required=True)
    clean_commit = clean_sub.add_parser("commit")
    _commit_args(clean_commit)

    recover = subparsers.add_parser("recover")
    recover_sub = recover.add_subparsers(dest="action", required=True)
    for action in ("verify", "rollback"):
        child = recover_sub.add_parser(action)
        _common(child)
        child.add_argument("--transaction", required=True)
    return parser


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True)
    parser.add_argument("--request-id")


def _commit_args(parser: argparse.ArgumentParser) -> None:
    _common(parser)
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--approval", required=True)


def _request(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "run":
        value = _load_json(args.request)
        if not isinstance(value, dict):
            raise ValueError("Protocol request must be a JSON object")
        return value

    request_id = args.request_id or f"cli-{uuid.uuid4().hex[:16]}"
    base: dict[str, Any] = {
        "protocol": 1,
        "request_id": request_id,
        "root": str(Path(args.root).absolute()),
    }
    if args.command in {"scan", "audit", "capability"}:
        base["kind"] = args.command
        if args.command == "scan":
            base["session_paths"] = args.session_path
            base["referenced_paths"] = args.referenced_path
        return base
    if args.command in {"init", "ledger", "clean"}:
        if args.action == "prepare":
            proposal = _load_json(args.proposal)
            if not isinstance(proposal, dict):
                raise ValueError("Proposal must be a JSON object")
            reserved = {"protocol", "request_id", "kind", "root"} & proposal.keys()
            if reserved:
                raise ValueError(f"Proposal cannot override reserved fields: {', '.join(sorted(reserved))}")
            kind = {"init": "prepare_initialize", "ledger": "prepare_ledger", "clean": "prepare_clean"}[args.command]
            return {**proposal, **base, "kind": kind}
        prepared = _load_json(args.prepared)
        approval = _load_json(args.approval)
        plan = _extract_plan(prepared)
        return {**base, "kind": "commit", "plan": plan, "approval": approval}
    if args.command == "recover":
        return {**base, "kind": f"recover_{args.action}", "transaction_id": args.transaction}
    raise ValueError("Unknown command")


def _extract_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Prepared input must be a JSON object")
    if "plan" in value and isinstance(value["plan"], dict):
        return value["plan"]
    details = value.get("details")
    if isinstance(details, dict):
        preview = details.get("plan_preview") or details
        if isinstance(preview, dict) and isinstance(preview.get("plan"), dict):
            return preview["plan"]
    raise ValueError("Prepared input does not contain a plan")


def _load_json(path: str) -> Any:
    if path == "-":
        text = sys.stdin.read(10 * 1024 * 1024 + 1)
    else:
        source = Path(path)
        if source.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("JSON input exceeds 10 MiB")
        text = source.read_text("utf-8")
    if len(text.encode("utf-8")) > 10 * 1024 * 1024:
        raise ValueError("JSON input exceeds 10 MiB")
    return json.loads(text, object_pairs_hook=_reject_duplicate_keys)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


if __name__ == "__main__":
    raise SystemExit(main())
