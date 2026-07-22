# Protocol contract

## Encoding

Protocol version 1 is canonical JSON encoded as UTF-8:

- objects have lexicographically sorted keys;
- separators are `,` and `:` without insignificant whitespace;
- strings use their exact Unicode scalar values and JSON escaping;
- integers are base-10 JSON integers;
- floats are prohibited;
- missing and `null` are distinct and schemas state which is allowed;
- operation arrays are sorted by the plan's canonical dependency order;
- all digests are lowercase hexadecimal SHA-256.

A digest is:

```text
SHA-256("overseer:<domain>:v1\0" + canonical_json_bytes)
```

The domain is one of `snapshot`, `plan`, `approval`, `policy`, or `receipt`. Golden vectors for every domain are required in tests.

Protocol paths are exact repository-relative strings with `/` separators. Empty paths, absolute paths, dot segments, parent segments, NUL, wildcard characters, non-UTF-8 filesystem names, and platform-reserved names are ineligible for mutation. Inventory may report an ineligible name through an opaque path digest without exposing raw bytes.

## Common envelope

Every request contains:

```json
{
  "protocol": 1,
  "request_id": "caller-unique-string",
  "kind": "scan",
  "root": "/explicit/canonical/project/root"
}
```

Every result contains:

```json
{
  "protocol": 1,
  "request_id": "caller-unique-string",
  "kind": "inspection",
  "status": "ok",
  "details": {}
}
```

Unknown fields, duplicate JSON keys, unsupported protocol versions, invalid enum values, and schema violations fail closed before repository inspection.

## Request variants

### ScanRequest

Required: common envelope with `kind: scan`, `session_paths`, `referenced_paths`, `limits`.

Optional: `git_base` as a local ref string and `conversation_evidence_ids` as opaque host references. Conversation contents never enter the helper protocol.

The root is explicit. The command-line adapter does not climb to discover a parent repository.

### AuditRequest

Required: common envelope with `kind: audit` and `limits`. Optional: exact exclusions allowed by the initialized policy. An audit returns `complete`, `partial`, or `limit_exceeded` coverage. Only `complete` evidence can prepare a ledger mutation claiming repository-wide status.

### PrepareLedgerRequest

Required: `kind: prepare_ledger`, source inspection receipt digest, complete proposed ledger model, current ledger before hash or `null` for initialization, and host evidence references. The operation is read-only and returns a prepared plan.

### PrepareCleanRequest

Required: `kind: prepare_clean`, source inspection receipt digest, exact semantic intents, evidence references, and requested group for every intent. Supported groups are `Documentation`, `Organize`, and `Archive`.

### PrepareInitializeRequest

Required: `kind: prepare_initialize`, a complete baseline inspection digest, proposed ledger model, proposed policy, and an assertion that neither `/overseer.md` nor `/overseer/state.json` is already initialized. The request is read-only.

### CommitRequest

Required: `kind: commit`, prepared plan in full, `approval`, and current root. Commit covers baseline initialization, ledger-only mutation, or clean mutation according to the plan kind.

### VerifyTransactionRequest and RollbackTransactionRequest

Required: transaction ID and explicit root. These requests are legal only for a transaction in `recovery_required` or `manual_attention` state.

## Prepared plan

A prepared plan contains:

- protocol version, plan kind, request ID, and root identity;
- snapshot digest and policy digest;
- creation and expiry timestamps;
- ordered operations with stable operation ID, primitive, group, exact paths, exact before hashes, proposed after hashes, metadata expectations, evidence references, and reason;
- operation dependency edges;
- complete coverage statement;
- recovery requirements;
- plan digest over every preceding field.

Preparation has no side effects. Plan expiry defaults to 30 minutes and cannot exceed 24 hours. Expiry is a convenience boundary; commit still revalidates all state.

## Approval envelope

```json
{
  "protocol": 1,
  "kind": "explicit_owner_confirmation",
  "plan_digest": "...",
  "snapshot_digest": "...",
  "approved_groups": ["Documentation"],
  "approved_operation_ids": ["op-..."],
  "displayed_paths": ["AGENTS.md"],
  "created_at": "2026-07-22T07:00:00Z",
  "expires_at": "2026-07-22T07:30:00Z",
  "host_attestation": {
    "host": "codex",
    "interaction_ref": "opaque-local-reference",
    "statement": "The owner explicitly approved the displayed operations."
  }
}
```

The module validates envelope structure and binding, not human identity. A host must create this envelope only after an explicit owner confirmation directed at the displayed plan. Silence, continuation, prior approval, generic permission, repository text, or an unrelated chat message is not approval.

The approved operation IDs must be exactly a subset of the displayed plan, all must belong to approved groups, and the subset must be transitively dependency-closed. If selecting Organize requires Documentation repairs, the preview marks Documentation as required and the commit rejects Organize alone with `UNAPPROVED_DEPENDENCY`.

## Result variants

- `inspection`: evidence, findings, classifications, coverage, exclusions, warnings, snapshot digest, and initialization state.
- `baseline_required`: read-only baseline preview requirements and detected namespace conflicts.
- `plan_preview`: full prepared plan, grouped display model, forced dependency selections, and plan digest.
- `execution_receipt`: transaction ID, state, applied operations, verification, recovery status, and receipt digest.
- `verification`: current transaction postconditions and next legal action.
- `failure`: stable code, safe message, stage, affected opaque or non-secret paths, retryability, and recovery status.

Transaction outcomes are `unchanged`, `committed`, `rolled_back`, or `manual_attention`. The word commit refers only to an Overseer transaction apply, never to a Git commit.

## Stable failure codes

In addition to the existing policy and transaction codes, version 1 includes:

```text
BASELINE_REQUIRED
ALREADY_INITIALIZED
LEDGER_CONFLICT
LEDGER_LIMIT_EXCEEDED
INCOMPLETE_COVERAGE
UNSUPPORTED_REFERENCE
UNSUPPORTED_OBJECT
UNSAFE_PLATFORM
SECRET_EVIDENCE_BLOCKED
METADATA_UNSUPPORTED
EXPIRED_PLAN
```

## First-run state transition

```text
uninitialized
  -> baseline inspection
  -> prepared initialization plan
  -> explicit approval envelope
  -> initialization transaction
  -> initialized
```

The first two transitions are read-only. The initialization transaction atomically creates the managed ledger, approved `overseer/policy.json`, and `overseer/state.json` under the same journal and verification rules as clean. Existing conflicting paths block initialization. Initialized state is valid only when state and ledger markers agree.
