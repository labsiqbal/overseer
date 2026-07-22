"""Dry-run plan construction and approval binding."""

from __future__ import annotations

import base64
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .common import digest, fail, parse_timestamp, sha256_bytes, sha256_file
from .inventory import find_exact_references, inventory
from .ledger import merge_ledger
from .paths import RootContext, checked_path, comparison_key, namespace_collisions, normalize_relative, path_identity
from .policy import Policy, can_operation, safe_path_label


ALLOWED_GROUPS = {"Ledger", "Documentation", "Organize", "Archive"}
PRIMITIVES = {"WriteLedger", "WritePolicy", "EditLivingDocument", "MoveExactPath", "ArchiveExactPath"}


def prepare_initialization(root: RootContext, request: dict[str, Any]) -> dict[str, Any]:
    if namespace_collisions(root):
        fail("ALREADY_INITIALIZED", "Overseer namespace already exists; inspect and resolve before initialization")
    policy = Policy.from_dict(request.get("policy"))
    evidence = inventory(root, policy, mode="audit")
    if evidence["coverage"] != "complete":
        fail("INCOMPLETE_COVERAGE", "Initialization requires a complete baseline inspection")
    ledger_bytes = merge_ledger(None, request["ledger_model"])
    policy_bytes = (_canonical_pretty(policy.as_dict()) + "\n").encode("utf-8")
    seed = {
        "kind": "initialize",
        "root_identity": root.identity,
        "snapshot_digest": evidence["snapshot_digest"],
        "ledger_hash": sha256_bytes(ledger_bytes),
        "policy_hash": sha256_bytes(policy_bytes),
    }
    transaction_id = digest("transaction-seed", seed)[:24]
    operations = [
        _write_operation("init-policy", "WritePolicy", "Documentation", "overseer/policy.json", None, policy_bytes, "Initialize approved Overseer policy"),
        _write_operation("init-ledger", "WriteLedger", "Ledger", "overseer.md", None, ledger_bytes, "Initialize approved context health baseline"),
    ]
    return _finalize_plan(
        root,
        "initialize",
        transaction_id,
        evidence["snapshot_digest"],
        policy.policy_digest,
        operations,
        coverage="complete",
        initialization_state={
            "protocol": 1,
            "initialized": True,
            "root_identity": root.persistent_identity,
            "policy_digest": policy.policy_digest,
            "latest_complete_fingerprint": evidence["snapshot_digest"],
            "finding_ids": [],
            "receipt_ids": [],
        },
    )


def prepare_ledger(root: RootContext, policy: Policy, request: dict[str, Any]) -> dict[str, Any]:
    path = checked_path(root, "overseer.md")
    if not stat.S_ISREG(path.lstat().st_mode):
        fail("BASELINE_REQUIRED", "overseer.md is missing; initialize the project first")
    before = path.read_bytes()
    after = merge_ledger(before, request["ledger_model"])
    if after == before:
        return {
            "protocol": 1,
            "kind": "plan_preview",
            "status": "unchanged",
            "plan": None,
            "reason": "Rendered ledger is byte-identical",
        }
    snapshot_digest = _validated_source_inspection(root, policy, request.get("source_inspection"))
    seed = {
        "kind": "ledger",
        "snapshot_digest": snapshot_digest,
        "before": sha256_bytes(before),
        "after": sha256_bytes(after),
    }
    transaction_id = digest("transaction-seed", seed)[:24]
    operation = _write_operation(
        request.get("operation_id", "ledger-update"),
        "WriteLedger",
        "Ledger",
        "overseer.md",
        before,
        after,
        request.get("reason", "Refresh project context health ledger"),
    )
    return _finalize_plan(root, "ledger", transaction_id, snapshot_digest, policy.policy_digest, [operation], coverage="complete")


def prepare_clean(root: RootContext, policy: Policy, request: dict[str, Any]) -> dict[str, Any]:
    intents = request.get("intents")
    if not isinstance(intents, list) or not intents:
        fail("INVALID_REQUEST", "Clean preparation requires a non-empty intents array")
    source_snapshot = _validated_source_inspection(root, policy, request.get("source_inspection"))

    proposal_seed = {"snapshot_digest": source_snapshot, "intents": intents, "root_identity": root.identity}
    transaction_id = digest("transaction-seed", proposal_seed)[:24]
    operations: list[dict[str, Any]] = []
    intent_ids: set[str] = set()
    document_repairs: dict[str, dict[str, Any]] = {}

    for index, intent in enumerate(intents):
        if not isinstance(intent, dict):
            fail("INVALID_REQUEST", f"Intent {index} must be an object")
        identifier = intent.get("id") or digest("intent", intent)[:16]
        if not isinstance(identifier, str) or not identifier or identifier in intent_ids:
            fail("INVALID_REQUEST", f"Intent IDs must be unique non-empty strings: {identifier}")
        intent_ids.add(identifier)
        kind = intent.get("kind")
        group = intent.get("group")
        if group not in {"Documentation", "Organize", "Archive"}:
            fail("INVALID_REQUEST", f"Invalid clean group for {identifier}: {group}")
        reason = intent.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            fail("INVALID_REQUEST", f"Intent {identifier} requires a reason")
        dependencies = intent.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
            fail("INVALID_REQUEST", f"Intent {identifier} has invalid depends_on")

        if kind == "edit_document":
            relative = normalize_relative(intent.get("path", ""))
            operation = _prepare_text_edit(root, policy, identifier, group, relative, intent, reason, dependencies)
            operations.append(operation)
            document_repairs[relative] = operation
        elif kind == "write_ledger":
            relative = "overseer.md"
            path = checked_path(root, relative)
            if not stat.S_ISREG(path.lstat().st_mode):
                fail("LEDGER_CONFLICT", "overseer.md must be a regular file")
            before = path.read_bytes() if path.exists() else None
            after = merge_ledger(before, intent["ledger_model"])
            operations.append(_write_operation(identifier, "WriteLedger", group, relative, before, after, reason, dependencies))
        elif kind == "write_policy":
            relative = "overseer/policy.json"
            path = checked_path(root, relative)
            if not stat.S_ISREG(path.lstat().st_mode):
                fail("PROTECTED_PATH", "Overseer policy must be a regular file")
            before = path.read_bytes() if path.exists() else None
            new_policy = Policy.from_dict(intent["policy"])
            after = (_canonical_pretty(new_policy.as_dict()) + "\n").encode("utf-8")
            operations.append(_write_operation(identifier, "WritePolicy", group, relative, before, after, reason, dependencies))
        elif kind in {"move", "archive"}:
            source = normalize_relative(intent.get("source", ""), allow_overseer=False)
            if kind == "move":
                destination = normalize_relative(intent.get("destination", ""), allow_overseer=False)
                primitive = "MoveExactPath"
            else:
                destination = f"overseer/archive/{datetime.now(timezone.utc).date().isoformat()}/{transaction_id}/{source}"
                primitive = "ArchiveExactPath"
            operation = _prepare_move(root, policy, identifier, primitive, group, source, destination, reason, dependencies, intent)
            operations.append(operation)
        else:
            fail("INVALID_REQUEST", f"Unsupported clean intent kind: {kind}")

    operation_ids = {operation["id"] for operation in operations}
    for operation in operations:
        missing = set(operation["dependencies"]) - operation_ids
        if missing:
            fail("INVALID_REQUEST", f"Operation {operation['id']} depends on unknown IDs: {', '.join(sorted(missing))}")

    policy_ops = [operation for operation in operations if operation["primitive"] == "WritePolicy"]
    if policy_ops and len(operations) != 1:
        fail("PROTECTED_PATH", "WritePolicy must be the only material operation in its transaction")

    move_ops = [operation for operation in operations if operation["primitive"] in {"MoveExactPath", "ArchiveExactPath"}]
    for operation in move_ops:
        replacement = operation.get("canonical_replacement") or operation["destination"]
        for referenced_by in find_exact_references(root, policy, operation["source"]):
            classification = policy.classify(referenced_by)
            repair = document_repairs.get(referenced_by)
            if classification.content_class != "living_context" or repair is None:
                fail(
                    "UNSUPPORTED_REFERENCE",
                    f"Move requires an approved supported reference repair in {referenced_by}",
                    details={"source": operation["source"], "referenced_by": referenced_by},
                )
            new_bytes = base64.b64decode(repair["content_b64"])
            if operation["source"].encode("utf-8") in new_bytes:
                fail("UNSUPPORTED_REFERENCE", f"Repair still contains old path in {referenced_by}")
            if replacement and replacement.encode("utf-8") not in new_bytes and operation["primitive"] == "MoveExactPath":
                fail("UNSUPPORTED_REFERENCE", f"Repair does not include new path in {referenced_by}")
            if repair["id"] not in operation["dependencies"]:
                operation["dependencies"].append(repair["id"])
                operation["dependencies"].sort()

    _reject_destination_aliases(operations)
    return _finalize_plan(root, "clean", transaction_id, source_snapshot, policy.policy_digest, operations, coverage="complete")


def validate_approval(plan: dict[str, Any], approval: dict[str, Any]) -> list[dict[str, Any]]:
    required = {
        "protocol", "kind", "plan_digest", "snapshot_digest", "approved_groups",
        "approved_operation_ids", "displayed_paths", "created_at", "expires_at", "host_attestation",
    }
    unknown = set(approval) - required
    missing = required - set(approval)
    if missing or unknown:
        fail("INVALID_REQUEST", f"Approval fields invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")
    if approval["protocol"] != 1 or approval["kind"] != "explicit_owner_confirmation":
        fail("APPROVAL_REQUIRED", "Approval must be protocol 1 explicit_owner_confirmation")
    if approval["plan_digest"] != plan["plan_digest"]:
        fail("PLAN_DIGEST_MISMATCH", "Approval plan digest does not match")
    if approval["snapshot_digest"] != plan["snapshot_digest"]:
        fail("STALE_SNAPSHOT", "Approval snapshot digest does not match")
    if parse_timestamp(approval["expires_at"]) < datetime.now(timezone.utc):
        fail("EXPIRED_PLAN", "Approval has expired")
    if parse_timestamp(approval["created_at"]) > parse_timestamp(approval["expires_at"]):
        fail("INVALID_REQUEST", "Approval expiry precedes creation")
    if parse_timestamp(approval["expires_at"]) > parse_timestamp(plan["expires_at"]):
        fail("APPROVAL_REQUIRED", "Approval cannot outlive the prepared plan")
    attestation = approval["host_attestation"]
    if not isinstance(attestation, dict) or attestation.get("statement") != "The owner explicitly approved the displayed operations.":
        fail("APPROVAL_REQUIRED", "Host attestation must state explicit owner approval")
    selected_ids = approval["approved_operation_ids"]
    selected_groups = approval["approved_groups"]
    if not isinstance(selected_ids, list) or not selected_ids or len(set(selected_ids)) != len(selected_ids):
        fail("APPROVAL_REQUIRED", "Approval must select unique operation IDs")
    if not isinstance(selected_groups, list) or not selected_groups or any(group not in ALLOWED_GROUPS for group in selected_groups):
        fail("APPROVAL_REQUIRED", "Approval groups are invalid")
    operation_map = {operation["id"]: operation for operation in plan["operations"]}
    if not set(selected_ids).issubset(operation_map):
        fail("APPROVAL_REQUIRED", "Approval contains unknown operation IDs")
    selected = [operation_map[identifier] for identifier in selected_ids]
    if any(operation["group"] not in selected_groups for operation in selected):
        fail("UNAPPROVED_GROUP", "Selected operations are not covered by selected groups")
    dependencies = {dependency for operation in selected for dependency in operation["dependencies"]}
    if not dependencies.issubset(selected_ids):
        fail("UNAPPROVED_DEPENDENCY", "Selected operations are not dependency-closed", details={"missing": sorted(dependencies - set(selected_ids))})
    expected_paths = sorted({path for operation in selected for path in _display_paths(operation)})
    if sorted(approval["displayed_paths"]) != expected_paths:
        fail("APPROVAL_REQUIRED", "Approval displayed paths do not match selected operations")
    return sorted(selected, key=_execution_key)


def validate_plan_digest(plan: dict[str, Any]) -> None:
    supplied = plan.get("plan_digest")
    unsigned = {key: value for key, value in plan.items() if key != "plan_digest"}
    if supplied != digest("plan", unsigned):
        fail("PLAN_DIGEST_MISMATCH", "Prepared plan digest is invalid")
    if parse_timestamp(plan["expires_at"]) < datetime.now(timezone.utc):
        fail("EXPIRED_PLAN", "Prepared plan has expired")


def _prepare_text_edit(
    root: RootContext,
    policy: Policy,
    identifier: str,
    group: str,
    relative: str,
    intent: dict[str, Any],
    reason: str,
    dependencies: list[str],
) -> dict[str, Any]:
    path = checked_path(root, relative)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        fail("UNSUPPORTED_OBJECT", f"Text edit requires a single-link regular file: {relative}")
    classification = policy.classify(relative, info.st_mode)
    if not can_operation(classification.content_class, "EditLivingDocument", relative):
        fail("PROTECTED_PATH", f"Content class cannot be edited: {relative}")
    before = path.read_bytes()
    _decode_supported_text(before, relative)
    new_content = intent.get("content")
    if not isinstance(new_content, str):
        fail("INVALID_REQUEST", f"Edit intent {identifier} requires string content")
    after = new_content.encode("utf-8")
    if before.startswith(b"\xef\xbb\xbf") and not after.startswith(b"\xef\xbb\xbf"):
        after = b"\xef\xbb\xbf" + after
    if b"\r\n" in before and b"\r\n" not in after:
        after = after.replace(b"\n", b"\r\n")
    if before == after:
        fail("INVALID_REQUEST", f"Edit intent {identifier} is a no-op")
    return _write_operation(identifier, "EditLivingDocument", group, relative, before, after, reason, dependencies, path)


def _prepare_move(
    root: RootContext,
    policy: Policy,
    identifier: str,
    primitive: str,
    group: str,
    source: str,
    destination: str,
    reason: str,
    dependencies: list[str],
    intent: dict[str, Any],
) -> dict[str, Any]:
    if primitive == "MoveExactPath" and group != "Organize":
        fail("INVALID_REQUEST", "MoveExactPath must be in Organize")
    if primitive == "ArchiveExactPath" and group != "Archive":
        fail("INVALID_REQUEST", "ArchiveExactPath must be in Archive")
    path = checked_path(root, source)
    info = path.lstat()
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
        fail("UNSUPPORTED_OBJECT", f"Move requires a regular file or symlink: {source}")
    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
        fail("UNSUPPORTED_OBJECT", f"Hard-linked files cannot be moved: {source}")
    if stat.S_ISLNK(info.st_mode):
        try:
            resolved_target = path.resolve(strict=False)
        except (OSError, RuntimeError):
            fail("UNSUPPORTED_OBJECT", f"Symlink target cannot be safely resolved: {source}")
        if not resolved_target.is_relative_to(root.path):
            fail("UNSUPPORTED_OBJECT", f"External symlink cannot be moved: {source}")
    classification = policy.classify(source, info.st_mode)
    if not can_operation(classification.content_class, primitive, source):
        fail("PROTECTED_PATH", f"Content class cannot be moved: {safe_path_label(source, classification)}")
    destination_path = root.path.joinpath(*destination.split("/"))
    if destination_path.exists() or destination_path.is_symlink():
        fail("DESTINATION_CONFLICT", f"Destination already exists: {destination}")
    created_parents = _missing_destination_parents(root, destination)
    before_hash = sha256_file(str(path)) if stat.S_ISREG(info.st_mode) else digest("symlink", os.readlink(path))
    return {
        "id": identifier,
        "primitive": primitive,
        "group": group,
        "source": source,
        "destination": destination,
        "before_hash": before_hash,
        "after_hash": before_hash,
        "before_identity": path_identity(path),
        "dependencies": sorted(set(dependencies)),
        "reason": reason.strip(),
        "canonical_replacement": intent.get("canonical_replacement"),
        "metadata": {"mode": stat.S_IMODE(info.st_mode), "type": "symlink" if stat.S_ISLNK(info.st_mode) else "file"},
        "created_parents": created_parents,
    }


def _write_operation(
    identifier: str,
    primitive: str,
    group: str,
    relative: str,
    before: bytes | None,
    after: bytes,
    reason: str,
    dependencies: list[str] | None = None,
    existing_path: Path | None = None,
) -> dict[str, Any]:
    if primitive not in PRIMITIVES:
        fail("INVALID_REQUEST", f"Unsupported primitive: {primitive}")
    metadata: dict[str, Any] = {"mode": 0o644}
    before_identity = None
    if existing_path is not None:
        info = existing_path.lstat()
        metadata = {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}
        before_identity = path_identity(existing_path)
    elif before is not None:
        path = Path(relative)
        metadata = {"mode": 0o644, "name": path.name}
    return {
        "id": identifier,
        "primitive": primitive,
        "group": group,
        "path": relative,
        "before_hash": sha256_bytes(before) if before is not None else None,
        "after_hash": sha256_bytes(after),
        "before_identity": before_identity,
        "content_b64": base64.b64encode(after).decode("ascii"),
        "dependencies": sorted(set(dependencies or [])),
        "reason": reason.strip(),
        "metadata": metadata,
    }


def _finalize_plan(
    root: RootContext,
    kind: str,
    transaction_id: str,
    snapshot_digest: str,
    policy_digest: str,
    operations: list[dict[str, Any]],
    *,
    coverage: str,
    initialization_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created = datetime.now(timezone.utc).replace(microsecond=0)
    operations = sorted(operations, key=lambda item: (item["group"], item.get("path", item.get("source", "")), item["id"]))
    plan: dict[str, Any] = {
        "protocol": 1,
        "kind": kind,
        "transaction_id": transaction_id,
        "root_identity": root.identity,
        "snapshot_digest": snapshot_digest,
        "policy_digest": policy_digest,
        "coverage": coverage,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "expires_at": (created + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "operations": operations,
    }
    if initialization_state is not None:
        plan["initialization_state"] = initialization_state
    plan["plan_digest"] = digest("plan", plan)
    return {"protocol": 1, "kind": "plan_preview", "status": "ok", "plan": plan}


def _execution_key(operation: dict[str, Any]) -> tuple[int, str, str]:
    order = {"MoveExactPath": 0, "ArchiveExactPath": 0, "WritePolicy": 1, "EditLivingDocument": 2, "WriteLedger": 3}
    path = operation.get("path", operation.get("source", ""))
    return order[operation["primitive"]], path, operation["id"]


def _display_paths(operation: dict[str, Any]) -> list[str]:
    if "path" in operation:
        return [operation["path"]]
    return [operation["source"], operation["destination"]]


def _reject_destination_aliases(operations: list[dict[str, Any]]) -> None:
    destinations: dict[str, str] = {}
    for operation in operations:
        destination = operation.get("destination")
        if not destination:
            continue
        key = comparison_key(destination)
        if key in destinations:
            fail("DESTINATION_CONFLICT", f"Destination aliases another planned destination: {destination}")
        destinations[key] = destination


def _missing_destination_parents(root: RootContext, destination: str) -> list[str]:
    parts = destination.split("/")[:-1]
    missing: list[str] = []
    current = root.path
    relative_parts: list[str] = []
    parent_missing = False
    for part in parts:
        relative_parts.append(part)
        current = current / part
        relative = "/".join(relative_parts)
        if parent_missing:
            missing.append(relative)
            continue
        try:
            info = current.lstat()
        except FileNotFoundError:
            parent_missing = True
            missing.append(relative)
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            fail("ROOT_ESCAPE", f"Destination parent is unsafe: {relative}")
    return missing


def _decode_supported_text(value: bytes, relative: str) -> str:
    try:
        return value.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("METADATA_UNSUPPORTED", f"Only UTF-8 text edits are supported: {relative}")


def _validated_source_inspection(root: RootContext, policy: Policy, value: Any) -> str:
    if not isinstance(value, dict):
        fail("INVALID_REQUEST", "source_inspection must be an inspection receipt")
    if value.get("coverage") != "complete":
        fail("INCOMPLETE_COVERAGE", "Preparation requires complete inspection coverage")
    scope = value.get("scope")
    if not isinstance(scope, dict) or scope.get("mode") not in {"scan", "audit"}:
        fail("INVALID_REQUEST", "source_inspection.scope must identify scan or audit")
    if scope["mode"] == "scan":
        current = inventory(
            root,
            policy,
            mode="scan",
            session_paths=scope.get("session_paths", []),
            referenced_paths=scope.get("referenced_paths", []),
        )
    else:
        current = inventory(root, policy, mode="audit")
    if current["coverage"] != "complete":
        fail("INCOMPLETE_COVERAGE", "Current inspection coverage is no longer complete")
    if value.get("snapshot_digest") != current["snapshot_digest"]:
        fail("STALE_SNAPSHOT", "Inspection receipt does not match current repository evidence")
    return current["snapshot_digest"]


def _canonical_pretty(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
