"""Recoverable, conflict-aware filesystem transactions."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any, Iterator

from .common import OverseerError, digest, fail, sha256_bytes, sha256_file, utc_now
from .paths import RootContext, checked_path, mutation_capability, normalize_relative, path_identity, secure_parent, stat_at
from .plans import validate_approval, validate_plan_digest
from .policy import Policy

try:
    import fcntl
except ImportError:  # Windows supports inspection and preview only in version 1.
    fcntl = None  # type: ignore[assignment]


def load_state(root: RootContext, *, required: bool = True) -> dict[str, Any] | None:
    path = root.path / "overseer" / "state.json"
    if not path.exists():
        if required:
            fail("BASELINE_REQUIRED", "Project is not initialized for Overseer")
        return None
    path = checked_path(root, "overseer/state.json")
    if not stat.S_ISREG(path.lstat().st_mode):
        fail("RECOVERY_REQUIRED", "Overseer state is not a regular file", stage="state", recovery_status="manual_attention")
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("RECOVERY_REQUIRED", f"Overseer state is unreadable: {exc}", stage="state", recovery_status="manual_attention")
    if value.get("protocol") != 1 or value.get("initialized") is not True:
        fail("RECOVERY_REQUIRED", "Overseer state is invalid", stage="state", recovery_status="manual_attention")
    _validate_root_identity(root, value.get("root_identity"))
    return value


def load_policy_dict(root: RootContext) -> dict[str, Any] | None:
    path = root.path / "overseer" / "policy.json"
    if not path.exists():
        return None
    path = checked_path(root, "overseer/policy.json")
    if not stat.S_ISREG(path.lstat().st_mode):
        fail("RECOVERY_REQUIRED", "Overseer policy is not a regular file", stage="state", recovery_status="manual_attention")
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("RECOVERY_REQUIRED", f"Overseer policy is unreadable: {exc}", stage="state", recovery_status="manual_attention")


def apply_plan(root: RootContext, plan: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    supported, reason = mutation_capability()
    if not supported:
        fail("UNSAFE_PLATFORM", reason, stage="capability")
    validate_plan_digest(plan)
    _validate_root_identity(root, plan.get("root_identity"))
    selected = validate_approval(plan, approval)
    if plan["kind"] == "initialize":
        if {operation["id"] for operation in selected} != {operation["id"] for operation in plan["operations"]}:
            fail("APPROVAL_REQUIRED", "Initialization requires approval of the complete prepared plan")
        if load_state(root, required=False) is not None:
            fail("ALREADY_INITIALIZED", "Project is already initialized")
    else:
        state = load_state(root)
        if state["policy_digest"] != plan["policy_digest"]:
            fail("STALE_SNAPSHOT", "Initialized policy changed after plan preparation")

    transaction_id = plan["transaction_id"]
    with _root_lock(root, create_namespace=plan["kind"] == "initialize"):
        _reject_other_recovery(root, transaction_id)
        transaction_dir = root.path / "overseer" / "transactions" / transaction_id
        if transaction_dir.exists() or transaction_dir.is_symlink():
            fail("DESTINATION_CONFLICT", "Transaction ID already exists")
        with secure_parent(root, f"overseer/transactions/{transaction_id}/journal.json", create_parents=True):
            pass
        os.chmod(transaction_dir, 0o700)
        (transaction_dir / "preimages").mkdir(mode=0o700)
        (transaction_dir / "staged").mkdir(mode=0o700)
        journal = {
            "protocol": 1,
            "transaction_id": transaction_id,
            "state": "preparing",
            "plan": plan,
            "approval_digest": digest("approval", approval),
            "selected_operation_ids": [operation["id"] for operation in selected],
            "applied_operation_ids": [],
            "current_operation_id": None,
            "state_created": False,
            "manifest_paths": [],
            "started_at": utc_now(),
            "finished_at": None,
            "error": None,
        }
        _write_journal(transaction_dir, journal)
        try:
            _capture_preimages(root, transaction_dir, selected)
            journal["state"] = "applying"
            _write_journal(transaction_dir, journal)
            for operation in selected:
                journal["current_operation_id"] = operation["id"]
                _write_journal(transaction_dir, journal)
                _apply_operation(root, transaction_dir, operation)
                journal["applied_operation_ids"].append(operation["id"])
                journal["current_operation_id"] = None
                _write_journal(transaction_dir, journal)
                if plan["kind"] == "initialize" and operation["primitive"] == "WritePolicy":
                    _write_internal_state(root, plan["initialization_state"])
                    journal["state_created"] = True
                    _write_journal(transaction_dir, journal)
            manifests = _write_archive_manifests(root, plan, approval, selected)
            journal["manifest_paths"] = manifests
            _write_journal(transaction_dir, journal)
            _verify_operations(root, selected)
            receipt = _commit_receipt(root, transaction_dir, journal, selected)
            _compact_internal_material(transaction_dir)
            return receipt
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if not journal["applied_operation_ids"] and journal["state"] in {"preparing", "applying"}:
                journal["state"] = "rolled_back"
                journal["finished_at"] = utc_now()
                journal["error"] = _safe_error(exc)
                _write_journal(transaction_dir, journal)
                _compact_internal_material(transaction_dir)
                if isinstance(exc, OverseerError):
                    raise exc
                raise
            journal["error"] = _safe_error(exc)
            journal["state"] = "rolling_back"
            _write_journal(transaction_dir, journal)
            recovery = _rollback(root, transaction_dir, journal)
            if recovery == "rolled_back":
                fail(
                    "IO_ERROR",
                    f"Transaction failed and was safely rolled back: {_safe_error(exc)}",
                    stage="apply",
                    retryable=True,
                    recovery_status="rolled_back",
                )
            fail(
                "RECOVERY_REQUIRED",
                f"Transaction failed and needs manual attention: {_safe_error(exc)}",
                stage="apply",
                recovery_status="manual_attention",
            )


def recover_verify(root: RootContext, transaction_id: str) -> dict[str, Any]:
    transaction_id = _transaction_id(transaction_id)
    with _root_lock(root):
        transaction_dir, journal = _load_journal(root, transaction_id)
        operations = _selected_operations(journal)
        _reconcile_current_operation(root, journal, operations)
        try:
            _verify_operations(root, operations)
        except OverseerError as exc:
            return {
                "protocol": 1,
                "kind": "verification",
                "status": "manual_attention",
                "transaction_id": transaction_id,
                "details": exc.as_details(),
                "next_action": "recover rollback",
            }
        receipt = _commit_receipt(root, transaction_dir, journal, operations)
        _compact_internal_material(transaction_dir)
        return receipt


def recover_rollback(root: RootContext, transaction_id: str) -> dict[str, Any]:
    transaction_id = _transaction_id(transaction_id)
    with _root_lock(root):
        transaction_dir, journal = _load_journal(root, transaction_id)
        operations = _selected_operations(journal)
        _reconcile_current_operation(root, journal, operations)
        outcome = _rollback(root, transaction_dir, journal)
        return {
            "protocol": 1,
            "kind": "verification",
            "status": outcome,
            "transaction_id": transaction_id,
            "next_action": "none" if outcome == "rolled_back" else "manual recovery",
        }


def pending_recovery(root: RootContext) -> list[str]:
    transactions = root.path / "overseer" / "transactions"
    if not transactions.is_dir():
        return []
    pending: list[str] = []
    for journal_path in transactions.glob("*/journal.json"):
        try:
            value = json.loads(journal_path.read_text("utf-8"))
        except Exception:
            pending.append(journal_path.parent.name)
            continue
        if value.get("state") not in {"committed", "rolled_back"}:
            pending.append(journal_path.parent.name)
    return sorted(pending)


@contextlib.contextmanager
def _root_lock(root: RootContext, *, create_namespace: bool = False) -> Iterator[None]:
    if fcntl is None:
        fail("UNSAFE_PLATFORM", "Advisory transaction locking is unavailable", stage="lock")
    if create_namespace:
        root_fd = os.open(root.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            root_info = os.fstat(root_fd)
            if (root_info.st_dev, root_info.st_ino) != (root.device, root.inode):
                fail("ROOT_ESCAPE", "Root identity changed before initialization", stage="lock")
            try:
                os.mkdir("overseer", 0o700, dir_fd=root_fd)
            except FileExistsError:
                fail("ALREADY_INITIALIZED", "Overseer namespace appeared after plan preparation", stage="lock")
        finally:
            os.close(root_fd)
    with secure_parent(root, "overseer/.lock") as (parent_fd, name):
        descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                fail("BUSY", "Another Overseer transaction holds the project lock", stage="lock", retryable=True)
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _capture_preimages(root: RootContext, transaction_dir: Path, operations: list[dict[str, Any]]) -> None:
    for operation in operations:
        primitive = operation["primitive"]
        if primitive in {"WriteLedger", "WritePolicy", "EditLivingDocument"}:
            relative = operation["path"]
            path = root.path.joinpath(*relative.split("/"))
            before_hash = operation["before_hash"]
            if before_hash is None:
                if path.exists() or path.is_symlink():
                    fail("STALE_SNAPSHOT", f"New write destination now exists: {relative}")
                continue
            _verify_regular_before(path, operation)
            data = path.read_bytes()
            if sha256_bytes(data) != before_hash:
                fail("STALE_SNAPSHOT", f"File changed after planning: {relative}")
            preimage = transaction_dir / "preimages" / f"{operation['id']}.bin"
            _write_private_file(preimage, data)
        else:
            source = root.path.joinpath(*operation["source"].split("/"))
            _verify_move_source(root, source, operation)
            destination = root.path.joinpath(*operation["destination"].split("/"))
            if destination.exists() or destination.is_symlink():
                fail("DESTINATION_CONFLICT", f"Destination appeared after planning: {operation['destination']}")


def _apply_operation(root: RootContext, transaction_dir: Path, operation: dict[str, Any]) -> None:
    primitive = operation["primitive"]
    if primitive in {"WriteLedger", "WritePolicy", "EditLivingDocument"}:
        content = base64.b64decode(operation["content_b64"], validate=True)
        if sha256_bytes(content) != operation["after_hash"]:
            fail("PLAN_DIGEST_MISMATCH", f"Operation content hash is invalid: {operation['id']}")
        _atomic_write(root, operation["path"], content, operation)
        return
    _secure_move(root, operation)


def _atomic_write(root: RootContext, relative: str, content: bytes, operation: dict[str, Any]) -> None:
    create_parents = operation["primitive"] == "WritePolicy"
    with secure_parent(root, relative, create_parents=create_parents) as (parent_fd, name):
        before_hash = operation["before_hash"]
        try:
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            exists = True
        except FileNotFoundError:
            info = None
            exists = False
        if before_hash is None:
            if exists:
                fail("STALE_SNAPSHOT", f"Write destination appeared: {relative}")
        else:
            if not exists or info is None or not stat.S_ISREG(info.st_mode):
                fail("STALE_SNAPSHOT", f"Write source changed type: {relative}")
            current = _read_at(parent_fd, name)
            if sha256_bytes(current) != before_hash:
                fail("STALE_SNAPSHOT", f"Write source changed: {relative}")
        temporary = f".overseer-{operation['id']}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600, dir_fd=parent_fd)
        try:
            _write_all(descriptor, content)
            os.fchmod(descriptor, operation["metadata"].get("mode", 0o644))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            os.fsync(parent_fd)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temporary, dir_fd=parent_fd)
            raise


def _secure_move(root: RootContext, operation: dict[str, Any]) -> None:
    source = operation["source"]
    destination = operation["destination"]
    try:
        with secure_parent(root, source) as (source_fd, source_name):
            _verify_at_move_source(root, source_fd, source_name, operation)
            with secure_parent(root, destination, create_parents=True) as (destination_fd, destination_name):
                try:
                    os.stat(destination_name, dir_fd=destination_fd, follow_symlinks=False)
                    fail("DESTINATION_CONFLICT", f"Destination appeared: {destination}")
                except FileNotFoundError:
                    pass
                os.rename(source_name, destination_name, src_dir_fd=source_fd, dst_dir_fd=destination_fd)
                os.fsync(source_fd)
                if destination_fd != source_fd:
                    os.fsync(destination_fd)
    except BaseException:
        _cleanup_created_parents(root, operation.get("created_parents", []))
        raise


def _verify_operations(root: RootContext, operations: list[dict[str, Any]]) -> None:
    for operation in operations:
        primitive = operation["primitive"]
        if primitive in {"WriteLedger", "WritePolicy", "EditLivingDocument"}:
            path = root.path.joinpath(*operation["path"].split("/"))
        else:
            source = root.path.joinpath(*operation["source"].split("/"))
            if source.exists() or source.is_symlink():
                fail("VERIFY_FAILED", f"Move source still exists: {operation['source']}", stage="verify")
            path = root.path.joinpath(*operation["destination"].split("/"))
        if not path.exists() and not path.is_symlink():
            fail("VERIFY_FAILED", f"Expected path is missing: {path.relative_to(root.path)}", stage="verify")
        current_hash = _content_hash(path)
        if current_hash != operation["after_hash"]:
            fail("VERIFY_FAILED", f"Post-operation hash mismatch: {path.relative_to(root.path)}", stage="verify")


def _rollback(root: RootContext, transaction_dir: Path, journal: dict[str, Any]) -> str:
    operations = {operation["id"]: operation for operation in journal["plan"]["operations"]}
    applied = list(journal.get("applied_operation_ids", []))
    current = journal.get("current_operation_id")
    if current and current not in applied:
        operation = operations[current]
        if _operation_after_holds(root, operation):
            applied.append(current)
    conflict = False
    for identifier in reversed(applied):
        operation = operations[identifier]
        try:
            if operation["primitive"] in {"WriteLedger", "WritePolicy", "EditLivingDocument"}:
                _rollback_write(root, transaction_dir, operation)
            else:
                _rollback_move(root, operation)
        except OverseerError:
            conflict = True
            break
    for relative in reversed(journal.get("manifest_paths", [])):
        path = root.path.joinpath(*relative.split("/"))
        with contextlib.suppress(OSError):
            if path.is_file() and _is_overseer_internal(relative):
                path.unlink()
    if journal.get("state_created"):
        state_path = root.path / "overseer" / "state.json"
        with contextlib.suppress(OSError):
            state_path.unlink()
    else:
        _restore_state_after_rollback(root, journal)
    journal["state"] = "manual_attention" if conflict else "rolled_back"
    journal["finished_at"] = utc_now()
    journal["current_operation_id"] = None
    _write_journal(transaction_dir, journal)
    if not conflict:
        _compact_internal_material(transaction_dir)
    return journal["state"]


def _rollback_write(root: RootContext, transaction_dir: Path, operation: dict[str, Any]) -> None:
    relative = operation["path"]
    path = root.path.joinpath(*relative.split("/"))
    if not path.exists():
        fail("ROLLBACK_CONFLICT", f"Written path disappeared: {relative}", stage="rollback", recovery_status="manual_attention")
    if _content_hash(path) != operation["after_hash"]:
        fail("ROLLBACK_CONFLICT", f"Written path changed externally: {relative}", stage="rollback", recovery_status="manual_attention")
    if operation["before_hash"] is None:
        if not _is_overseer_internal(relative) and relative != "overseer.md":
            fail("ROLLBACK_CONFLICT", f"Refusing to unlink non-internal path: {relative}", stage="rollback")
        with secure_parent(root, relative) as (parent_fd, name):
            os.unlink(name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        return
    preimage = transaction_dir / "preimages" / f"{operation['id']}.bin"
    if not preimage.is_file():
        fail("ROLLBACK_CONFLICT", f"Preimage is missing: {operation['id']}", stage="rollback")
    data = preimage.read_bytes()
    if sha256_bytes(data) != operation["before_hash"]:
        fail("ROLLBACK_CONFLICT", f"Preimage hash mismatch: {operation['id']}", stage="rollback")
    reverse = dict(operation)
    reverse["before_hash"] = operation["after_hash"]
    reverse["after_hash"] = operation["before_hash"]
    _atomic_write(root, relative, data, reverse)


def _rollback_move(root: RootContext, operation: dict[str, Any]) -> None:
    source = operation["source"]
    destination = operation["destination"]
    source_path = root.path.joinpath(*source.split("/"))
    destination_path = root.path.joinpath(*destination.split("/"))
    if source_path.exists() or source_path.is_symlink():
        fail("ROLLBACK_CONFLICT", f"Original source was recreated: {source}", stage="rollback")
    if not destination_path.exists() and not destination_path.is_symlink():
        fail("ROLLBACK_CONFLICT", f"Moved destination disappeared: {destination}", stage="rollback")
    if _content_hash(destination_path) != operation["after_hash"]:
        fail("ROLLBACK_CONFLICT", f"Moved destination changed externally: {destination}", stage="rollback")
    reverse = dict(operation)
    reverse["source"] = destination
    reverse["destination"] = source
    reverse["before_hash"] = operation["after_hash"]
    reverse["after_hash"] = operation["before_hash"]
    reverse["created_parents"] = []
    _secure_move(root, reverse)
    _cleanup_created_parents(root, operation.get("created_parents", []))


def _write_archive_manifests(
    root: RootContext,
    plan: dict[str, Any],
    approval: dict[str, Any],
    operations: list[dict[str, Any]],
) -> list[str]:
    archive_operations = [operation for operation in operations if operation["primitive"] == "ArchiveExactPath"]
    if not archive_operations:
        return []
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for operation in archive_operations:
        transaction_root = "/".join(operation["destination"].split("/")[:4])
        by_parent.setdefault(transaction_root, []).append(operation)
    paths: list[str] = []
    for parent, entries in by_parent.items():
        relative = f"{parent}/manifest.json"
        value = {
            "protocol": 1,
            "transaction_id": plan["transaction_id"],
            "created_at": utc_now(),
            "approval_digest": digest("approval", approval),
            "entries": [
                {
                    "original_path": operation["source"],
                    "archived_path": operation["destination"],
                    "content_hash": operation["after_hash"],
                    "metadata": operation["metadata"],
                    "reason": operation["reason"],
                    "canonical_replacement": operation.get("canonical_replacement"),
                }
                for operation in sorted(entries, key=lambda item: item["source"])
            ],
        }
        _atomic_internal_json(root, relative, value)
        paths.append(relative)
    return paths


def _commit_receipt(
    root: RootContext,
    transaction_dir: Path,
    journal: dict[str, Any],
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    state = load_state(root, required=False)
    if state is not None:
        receipts = [item for item in state.get("receipt_ids", []) if item != journal["transaction_id"]]
        receipts.append(journal["transaction_id"])
        state["receipt_ids"] = receipts[-20:]
        if any(operation["primitive"] == "WritePolicy" for operation in operations):
            policy_operation = next(operation for operation in operations if operation["primitive"] == "WritePolicy")
            policy_value = json.loads(base64.b64decode(policy_operation["content_b64"]).decode("utf-8"))
            state["policy_digest"] = Policy.from_dict(policy_value).policy_digest
        _write_internal_state(root, state)
    journal["state"] = "committed"
    journal["finished_at"] = utc_now()
    journal["current_operation_id"] = None
    _write_journal(transaction_dir, journal)
    receipt_details = {
        "transaction_id": journal["transaction_id"],
        "state": "committed",
        "applied_operation_ids": [operation["id"] for operation in operations],
        "verification": "passed",
        "journal": f"overseer/transactions/{journal['transaction_id']}/journal.json",
    }
    return {
        "protocol": 1,
        "kind": "execution_receipt",
        "status": "committed",
        "details": {**receipt_details, "receipt_digest": digest("receipt", receipt_details)},
    }


def _write_internal_state(root: RootContext, state: dict[str, Any]) -> None:
    _atomic_internal_json(root, "overseer/state.json", state)


def _atomic_internal_json(root: RootContext, relative: str, value: Any) -> None:
    if not _is_overseer_internal(relative):
        fail("PROTECTED_PATH", f"Internal write escaped Overseer namespace: {relative}")
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    operation = {
        "id": digest("internal-write", relative)[:16],
        "primitive": "WritePolicy",
        "before_hash": None,
        "after_hash": sha256_bytes(content),
        "metadata": {"mode": 0o600},
    }
    path = root.path.joinpath(*relative.split("/"))
    if path.exists():
        operation["before_hash"] = sha256_file(str(path))
    _atomic_write(root, relative, content, operation)


def _write_journal(transaction_dir: Path, journal: dict[str, Any]) -> None:
    path = transaction_dir / "journal.json"
    temporary = transaction_dir / ".journal.tmp"
    data = json.dumps(journal, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    directory_fd = os.open(transaction_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _compact_internal_material(transaction_dir: Path) -> None:
    for name in ("preimages", "staged"):
        target = transaction_dir / name
        if target.is_dir() and target.parent == transaction_dir:
            with contextlib.suppress(OSError):
                shutil.rmtree(target)


def _reject_other_recovery(root: RootContext, current: str) -> None:
    pending = [identifier for identifier in pending_recovery(root) if identifier != current]
    if pending:
        fail("RECOVERY_REQUIRED", "Another transaction requires recovery", recovery_status="manual_attention", details={"transactions": pending})


def _load_journal(root: RootContext, transaction_id: str) -> tuple[Path, dict[str, Any]]:
    transaction_dir = root.path / "overseer" / "transactions" / transaction_id
    path = transaction_dir / "journal.json"
    path = checked_path(root, f"overseer/transactions/{transaction_id}/journal.json")
    if not stat.S_ISREG(path.lstat().st_mode):
        fail("RECOVERY_REQUIRED", "Recovery journal is not a regular file", recovery_status="manual_attention")
    try:
        journal = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("RECOVERY_REQUIRED", f"Cannot load recovery journal: {exc}", recovery_status="manual_attention")
    if journal.get("transaction_id") != transaction_id:
        fail("RECOVERY_REQUIRED", "Recovery journal identity mismatch", recovery_status="manual_attention")
    if journal.get("state") in {"committed", "rolled_back"}:
        fail("INVALID_REQUEST", f"Transaction is already {journal['state']}")
    return transaction_dir, journal


def _selected_operations(journal: dict[str, Any]) -> list[dict[str, Any]]:
    selected = set(journal["selected_operation_ids"])
    return [operation for operation in journal["plan"]["operations"] if operation["id"] in selected]


def _reconcile_current_operation(root: RootContext, journal: dict[str, Any], operations: list[dict[str, Any]]) -> None:
    current = journal.get("current_operation_id")
    if not current or current in journal.get("applied_operation_ids", []):
        return
    operation = next((item for item in operations if item["id"] == current), None)
    if operation is None:
        fail("RECOVERY_REQUIRED", "Journal current operation is unknown", recovery_status="manual_attention")
    if _operation_after_holds(root, operation):
        journal["applied_operation_ids"].append(current)
        return
    if not _operation_before_holds(root, operation):
        fail("ROLLBACK_CONFLICT", "Current operation is neither before nor after state", recovery_status="manual_attention")


def _operation_after_holds(root: RootContext, operation: dict[str, Any]) -> bool:
    if operation["primitive"] in {"WriteLedger", "WritePolicy", "EditLivingDocument"}:
        path = root.path.joinpath(*operation["path"].split("/"))
        return path.exists() and _content_hash(path) == operation["after_hash"]
    source = root.path.joinpath(*operation["source"].split("/"))
    destination = root.path.joinpath(*operation["destination"].split("/"))
    return not source.exists() and destination.exists() and _content_hash(destination) == operation["after_hash"]


def _operation_before_holds(root: RootContext, operation: dict[str, Any]) -> bool:
    if operation["primitive"] in {"WriteLedger", "WritePolicy", "EditLivingDocument"}:
        path = root.path.joinpath(*operation["path"].split("/"))
        if operation["before_hash"] is None:
            return not path.exists()
        return path.exists() and _content_hash(path) == operation["before_hash"]
    source = root.path.joinpath(*operation["source"].split("/"))
    destination = root.path.joinpath(*operation["destination"].split("/"))
    return source.exists() and not destination.exists() and _content_hash(source) == operation["before_hash"]


def _verify_regular_before(path: Path, operation: dict[str, Any]) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        fail("STALE_SNAPSHOT", f"Text source changed object type: {path}")
    expected = operation.get("before_identity")
    if expected and path_identity(path) != expected:
        fail("STALE_SNAPSHOT", f"Text source identity changed: {path}")


def _verify_move_source(root: RootContext, path: Path, operation: dict[str, Any]) -> None:
    if not path.exists() and not path.is_symlink():
        fail("STALE_SNAPSHOT", f"Move source disappeared: {operation['source']}")
    if path_identity(path) != operation["before_identity"]:
        fail("STALE_SNAPSHOT", f"Move source identity changed: {operation['source']}")
    if _content_hash(path) != operation["before_hash"]:
        fail("STALE_SNAPSHOT", f"Move source content changed: {operation['source']}")
    if path.is_symlink():
        try:
            resolved_target = path.resolve(strict=False)
            resolved_target.relative_to(root.path)
        except (OSError, RuntimeError, ValueError):
            fail("STALE_SNAPSHOT", f"Symlink target is no longer safely inside the project: {operation['source']}")


def _verify_at_move_source(root: RootContext, parent_fd: int, name: str, operation: dict[str, Any]) -> None:
    info = stat_at(parent_fd, name)
    current_identity = {"device": info.st_dev, "inode": info.st_ino, "mode": stat.S_IFMT(info.st_mode), "size": info.st_size}
    if current_identity != operation["before_identity"]:
        fail("STALE_SNAPSHOT", f"Move source changed before operation: {operation['source']}")
    current = _hash_at(parent_fd, name, info.st_mode)
    if current != operation["before_hash"]:
        fail("STALE_SNAPSHOT", f"Move source hash changed before operation: {operation['source']}")
    if stat.S_ISLNK(info.st_mode):
        path = root.path.joinpath(*operation["source"].split("/"))
        try:
            path.resolve(strict=False).relative_to(root.path)
        except (OSError, RuntimeError, ValueError):
            fail("STALE_SNAPSHOT", f"Symlink target escaped the project before operation: {operation['source']}")


def _hash_at(parent_fd: int, name: str, mode: int) -> str:
    if stat.S_ISLNK(mode):
        target = os.readlink(name, dir_fd=parent_fd)
        return digest("symlink", target)
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        value = __import__("hashlib").sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            value.update(chunk)
        return value.hexdigest()
    finally:
        os.close(descriptor)


def _content_hash(path: Path) -> str:
    if path.is_symlink():
        return digest("symlink", os.readlink(path))
    return sha256_file(str(path))


def _read_at(parent_fd: int, name: str) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_private_file(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:
            raise OSError("Short write")
        offset += written


def _safe_error(exc: BaseException) -> str:
    if isinstance(exc, OverseerError):
        return f"{exc.code}: {exc.message}"
    return f"{type(exc).__name__}: {exc}"


def _validate_root_identity(root: RootContext, value: Any) -> None:
    if not isinstance(value, dict):
        fail("ROOT_ESCAPE", "Prepared or initialized root identity is missing")
    expected = root.identity if "path" in value else root.persistent_identity
    if value != expected:
        fail("ROOT_ESCAPE", "Root identity does not match prepared state")


def _transaction_id(value: str) -> str:
    if not isinstance(value, str) or not value or any(char not in "0123456789abcdef" for char in value):
        fail("INVALID_REQUEST", "Transaction ID must be lowercase hexadecimal")
    return value


def _is_overseer_internal(relative: str) -> bool:
    normalized = normalize_relative(relative)
    return normalized.startswith("overseer/")


def _restore_state_after_rollback(root: RootContext, journal: dict[str, Any]) -> None:
    state_path = root.path / "overseer" / "state.json"
    try:
        state = json.loads(state_path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    state["policy_digest"] = journal["plan"]["policy_digest"]
    state["receipt_ids"] = [
        identifier for identifier in state.get("receipt_ids", []) if identifier != journal["transaction_id"]
    ]
    with contextlib.suppress(OverseerError, OSError):
        _write_internal_state(root, state)


def _cleanup_created_parents(root: RootContext, relatives: list[str]) -> None:
    for relative in sorted(relatives, key=lambda item: item.count("/"), reverse=True):
        try:
            with secure_parent(root, relative) as (parent_fd, name):
                os.rmdir(name, dir_fd=parent_fd)
                os.fsync(parent_fd)
        except (OSError, OverseerError):
            continue
