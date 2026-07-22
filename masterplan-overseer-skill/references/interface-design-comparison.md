# Interface design comparison

## Design goal

The architectural seam is between semantic judgment by the host AI agent and deterministic repository operations by Overseer's local Python module. The host decides what repository evidence means, proposes remediation, explains it to the owner, and obtains approval. The Python module inventories files, validates exact-path plans, binds approval to repository state, executes allowed operations, journals mutations, and verifies the result.

The module must remain deep: callers should learn a small interface while the implementation hides path safety, Git evidence, hashing, reference checks, approval validation, transaction recovery, and ledger rendering.

## Option A - Minimal three-stage protocol

External interface:

```python
result = run(Start(...) | Prepare(...) | Commit(...))
```

- `Start` captures repository evidence for `scan` or `audit`.
- `Prepare` validates a host-proposed remediation and returns an immutable preview.
- `Commit` applies an approved prepared plan.
- Opaque run and plan tokens prevent callers from skipping stages.

Strengths:

- The smallest public surface.
- Read and write phases are unmistakably separate.
- Approval is naturally bound to one prepared plan.
- Safety policy remains highly local to one module.

Weaknesses:

- Generic stage names hide the familiar `scan`, `audit`, and `clean` vocabulary.
- Tokens create more protocol state for simple command-line callers.
- Recovery and verification need to be added to the same union or exposed elsewhere.

## Option B - Mode-first common-caller interface

External interface:

```python
result = run({"mode": "scan" | "audit" | "clean", ...})
```

Command-line form:

```text
python3 -m overseer scan
python3 -m overseer audit
python3 -m overseer clean --plan candidate.json
```

- A zero-argument `scan` is optimized for the most frequent caller.
- The first `clean` call always previews.
- A second `clean` call supplies the exact prepared plan and approval tokens.
- Structured JSON responses and stable exit codes support any agent host.

Strengths:

- Easy to discover and explain.
- Directly matches the public product language.
- The ordinary caller needs one function and three mode names.
- The same request shape works in-process and over a command-line adapter.

Weaknesses:

- Reusing `clean` for both preview and commit makes the phase transition less explicit.
- A loose dictionary contract can become ambiguous unless strictly versioned and validated.
- Prepared plans are intentionally verbose.

## Option C - Protocol-first extensible engine

External interface:

```python
engine = Overseer.open(root)
result = engine.handle(request)
```

- One versioned request and response protocol covers modes, previews, commits, verification, and rollback.
- Detector adapters inspect immutable snapshots.
- Operation adapters lower semantic intents into a closed primitive set.
- Extensions cannot receive direct filesystem mutation capability.

Strengths:

- Best-defined recovery and fault model.
- Snapshot and plan digests make stale approval difficult to misuse.
- Immutable snapshots and closed primitives preserve the safety boundary.
- New first-party detectors can be added without changing ordinary callers.

Weaknesses:

- The extension seam is more surface area than version 1 requires.
- Custom Python extensions cannot be meaningfully sandboxed in-process.
- A single generic envelope is less discoverable than typed request variants.

## Decision - typed mode requests over one deep module

Overseer adopts a hybrid of Options A and B, with the recovery discipline from Option C.

The public Python seam is one function:

```python
from overseer_core import run

result = run(request)
```

The closed request union is:

```text
ScanRequest
AuditRequest
PrepareInitializeRequest
PrepareLedgerRequest
PrepareCleanRequest
CommitRequest
VerifyTransactionRequest
RollbackTransactionRequest
```

The ordinary host uses the product modes `scan`, `audit`, and `clean`. Internally, `clean` is intentionally split into `prepare` and `commit` so a mutation cannot be hidden behind an option flag. Every response is canonical JSON with a protocol version, request ID, result kind, stable status, and structured details.

The command-line adapter preserves the short public vocabulary:

```text
python3 scripts/overseer.py scan --root PATH [--session FILE]
python3 scripts/overseer.py audit --root PATH
python3 scripts/overseer.py init prepare --root PATH --proposal FILE
python3 scripts/overseer.py init commit --root PATH --prepared FILE --approval FILE
python3 scripts/overseer.py ledger prepare --root PATH --proposal FILE
python3 scripts/overseer.py ledger commit --root PATH --prepared FILE --approval FILE
python3 scripts/overseer.py clean prepare --root PATH --proposal FILE
python3 scripts/overseer.py clean commit --root PATH --prepared FILE --approval FILE
python3 scripts/overseer.py recover verify --root PATH --transaction ID
python3 scripts/overseer.py recover rollback --root PATH --transaction ID
```

The host-facing skill normally invokes these commands and translates structured results into a concise human interaction. Users should not need to know the recovery commands unless a transaction is interrupted.

## Closed mutation vocabulary

Version 1 supports five primitives only:

```text
WriteLedger
WritePolicy
EditLivingDocument
MoveExactPath
ArchiveExactPath
```

There is no delete, shell, callback, glob, repository-root, arbitrary-write, or network primitive. `WritePolicy` can target only `/overseer/policy.json`, must be the sole material operation in its transaction, and becomes effective only after verification and a new inspection. Semantic artifact types remain a host-agent concern. New detectors may improve evidence collection later, but every mutation must still lower into this closed vocabulary and pass the same policy engine.

Public third-party detector or operation plugins are deferred. This keeps the trust boundary small. First-party detectors remain internal modules over immutable snapshots and can evolve without expanding the caller interface.

## Core invariants

- Dry run is the default and the prepare stage is always read-only.
- Every source and destination is an exact normalized repository-relative path.
- Root paths, globs, unresolved parent traversal, and paths escaping through symlinks are rejected.
- Permanent deletion is impossible because no delete primitive exists.
- Archive destinations are derived by the module under `overseer/archive/YYYY-MM-DD/<transaction-id>/<original-relative-path>`.
- `scan` and `audit` can prepare only an approved `WriteLedger` operation.
- Documentation, Organize, and Archive are independently approvable clean groups.
- A partial approval is accepted only when its operation dependencies are also approved.
- The snapshot digest, plan digest, approved groups, approved operation IDs, and exact before hashes must all match at transaction apply time.
- The journal is durable before the first mutation and `/overseer.md` is written last.
- A failed operation rolls back in reverse order. A conflicting external edit is never overwritten during rollback.
- An unresolved journal blocks later mutation until verification or rollback finishes.

## Internal adapters

Adapters exist only where the environment genuinely varies:

- filesystem: local production adapter and fault-injecting test adapter;
- Git evidence: local Git subprocess adapter and no-Git adapter;
- runtime: system clock and IDs, plus deterministic test values.

All policy, planning, dependency ordering, canonical serialization, journaling, rollback, and verification remain in the core module. This locality ensures that every caller and every detector receives the same safety behavior.

## Stable failure classes

The protocol uses stable codes rather than requiring callers to match prose:

```text
INVALID_REQUEST
UNSUPPORTED_PROTOCOL
ROOT_ESCAPE
SYMLINK_CONTENT_WRITE
PROTECTED_PATH
LIMIT_EXCEEDED
STALE_SNAPSHOT
PLAN_DIGEST_MISMATCH
APPROVAL_REQUIRED
UNAPPROVED_GROUP
UNAPPROVED_DEPENDENCY
DESTINATION_CONFLICT
BUSY
IO_ERROR
VERIFY_FAILED
RECOVERY_REQUIRED
ROLLBACK_CONFLICT
```

Human-readable messages may improve over time without changing automation behavior.
