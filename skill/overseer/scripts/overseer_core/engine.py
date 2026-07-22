"""Versioned request router for the Overseer kernel."""

from __future__ import annotations

from typing import Any

from .common import OverseerError, PROTOCOL_VERSION, fail, require_fields
from .inventory import inventory
from .paths import mutation_capability, namespace_collisions, open_root
from .plans import prepare_clean, prepare_initialization, prepare_ledger
from .policy import Policy
from .transactions import (
    apply_plan,
    load_policy_dict,
    load_state,
    pending_recovery,
    recover_rollback,
    recover_verify,
)


COMMON = {"protocol", "request_id", "kind", "root"}


def run(request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("request_id", "unknown") if isinstance(request, dict) else "unknown"
    try:
        return _run(request)
    except OverseerError as exc:
        return {
            "protocol": PROTOCOL_VERSION,
            "request_id": request_id,
            "kind": "failure",
            "status": "error",
            "details": exc.as_details(),
        }
    except Exception as exc:
        return {
            "protocol": PROTOCOL_VERSION,
            "request_id": request_id,
            "kind": "failure",
            "status": "error",
            "details": {
                "code": "IO_ERROR",
                "message": f"Unexpected local failure: {type(exc).__name__}: {exc}",
                "stage": "internal",
                "retryable": False,
                "recovery_status": "none",
            },
        }


def _run(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        fail("INVALID_REQUEST", "Request must be a JSON object")
    if request.get("protocol") != PROTOCOL_VERSION:
        fail("UNSUPPORTED_PROTOCOL", "Only protocol version 1 is supported")
    if not isinstance(request.get("request_id"), str) or not request["request_id"]:
        fail("INVALID_REQUEST", "request_id must be a non-empty string")
    root = open_root(request.get("root"))
    kind = request.get("kind")

    if kind == "capability":
        require_fields(request, required=COMMON)
        supported, reason = mutation_capability()
        return _success(request, "capability", {"mutation_supported": supported, "reason": reason, "root_identity": root.identity})

    if kind in {"scan", "audit"}:
        optional = {"session_paths", "referenced_paths"} if kind == "scan" else set()
        require_fields(request, required=COMMON, optional=optional)
        state = load_state(root, required=False)
        if state is None:
            policy = Policy.default()
            evidence = inventory(
                root,
                policy,
                mode=kind,
                session_paths=request.get("session_paths", []),
                referenced_paths=request.get("referenced_paths", []),
            )
            return _success(
                request,
                "baseline_required",
                {
                    "initialized": False,
                    "message": "Inspect this read-only evidence, resolve namespace conflicts, then prepare initialization",
                    "inspection": evidence,
                    "collisions": namespace_collisions(root),
                },
            )
        policy = _loaded_policy(root, state)
        evidence = inventory(
            root,
            policy,
            mode=kind,
            session_paths=request.get("session_paths", []),
            referenced_paths=request.get("referenced_paths", []),
        )
        recovery = pending_recovery(root)
        if recovery:
            evidence["warnings"].append("Mutation is blocked until pending transaction recovery completes")
            evidence["recovery_required"] = recovery
        return _success(request, "inspection", {"initialized": True, **evidence})

    if kind == "prepare_initialize":
        require_fields(request, required=COMMON | {"ledger_model"}, optional={"policy"})
        if load_state(root, required=False) is not None:
            fail("ALREADY_INITIALIZED", "Project is already initialized")
        preview = prepare_initialization(root, request)
        return _success(request, preview["kind"], preview)

    if kind == "prepare_ledger":
        require_fields(
            request,
            required=COMMON | {"ledger_model", "source_inspection"},
            optional={"operation_id", "reason"},
        )
        state = load_state(root)
        policy = _loaded_policy(root, state)
        preview = prepare_ledger(root, policy, request)
        return _success(request, preview["kind"], preview)

    if kind == "prepare_clean":
        require_fields(request, required=COMMON | {"intents", "source_inspection"})
        state = load_state(root)
        policy = _loaded_policy(root, state)
        preview = prepare_clean(root, policy, request)
        return _success(request, preview["kind"], preview)

    if kind == "commit":
        require_fields(request, required=COMMON | {"plan", "approval"})
        receipt = apply_plan(root, request["plan"], request["approval"])
        return _success(request, receipt["kind"], receipt)

    if kind == "recover_verify":
        require_fields(request, required=COMMON | {"transaction_id"})
        return _success(request, "verification", recover_verify(root, request["transaction_id"]))

    if kind == "recover_rollback":
        require_fields(request, required=COMMON | {"transaction_id"})
        return _success(request, "verification", recover_rollback(root, request["transaction_id"]))

    fail("INVALID_REQUEST", f"Unsupported request kind: {kind}")


def _loaded_policy(root: Any, state: dict[str, Any]) -> Policy:
    policy = Policy.from_dict(load_policy_dict(root))
    if policy.policy_digest != state.get("policy_digest"):
        fail("RECOVERY_REQUIRED", "Policy digest does not match initialized state", stage="state", recovery_status="manual_attention")
    return policy


def _success(request: dict[str, Any], kind: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL_VERSION,
        "request_id": request["request_id"],
        "kind": kind,
        "status": "ok" if details.get("status") != "unchanged" else "unchanged",
        "details": details,
    }
