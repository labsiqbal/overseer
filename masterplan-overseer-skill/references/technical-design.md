# Technical design

## System boundary

Overseer is an Agent Skill backed by a dependency-free local Python module. It is not a daemon, application, database, scheduler, or agent runtime.

The host AI agent owns semantic work:

- interpret the current conversation and repository evidence;
- distinguish canonical, duplicated, superseded, stale, and ambiguous context;
- draft concise changes to living documents and `/overseer.md`;
- explain proposed remediation to the owner;
- obtain explicit approval for the presented groups.

The deterministic module owns mechanical guarantees:

- repository inventory and bounded hashing;
- optional local Git evidence;
- Markdown reference inspection;
- exact-path plan validation;
- root confinement and protected-path policy;
- canonical plan and snapshot digests;
- dry-run previews;
- archive destination derivation;
- transaction locks, journals, rollback, and verification;
- canonical JSON input and output.

This seam prevents natural-language interpretation from becoming filesystem authority.

## Repository package layout

```text
SKILL.md
LICENSE
agents/
  openai.yaml
scripts/
  overseer.py
  overseer_core/
    __init__.py
    protocol.py
    engine.py
    inventory.py
    git_evidence.py
    references.py
    policy.py
    plans.py
    transactions.py
    ledger.py
    adapters.py
references/
  policy.md
  protocol.md
  ledger-format.md
assets/
  overseer-template.md
tests/
  fixtures/
  test_protocol.py
  test_inventory.py
  test_policy.py
  test_transactions.py
  test_cli_e2e.py
```

`SKILL.md` stays concise and routes the host to the appropriate reference only when needed. The Python package is private implementation behind `scripts/overseer.py`; users invoke the skill, not a general-purpose library.

## Runtime data layout in a managed project

```text
overseer.md
overseer/
  state.json
  transactions/
    <transaction-id>/
      journal.json
      preimages/
      staged/
  archive/
    YYYY-MM-DD/
      <transaction-id>/
        <original-relative-path>
        manifest.json
```

`overseer.md` is the only root-level file owned by Overseer. It is the human-readable and AI-readable context health ledger.

`overseer/state.json` is bounded machine state. It stores the schema version, latest successful evidence fingerprint, known finding identifiers, and hashes needed to suppress unchanged results. It never stores file contents, conversation transcripts, secrets, absolute paths, or a second prose index.

Transaction preimages and staging bytes are retained only when recovery is required and are removed after verified completion. Successfully committed journals become bounded receipts. Each transaction-qualified archive boundary has a manifest containing original path, archived path, content hash, reason, canonical replacement if known, approval reference, and transaction ID.

No SQLite database or background index is used.

## Protocol and lifecycle

Protocol version 1 uses canonical JSON. Unknown versions and unknown fields fail closed. Field-level schemas, digest construction, approval envelopes, and first-run transitions are defined in `protocol-contract.md`.

### Scan

1. The host supplies an explicit project root, session paths, referenced paths, and optional Git base evidence.
2. The module validates paths and captures a scoped immutable snapshot.
3. It returns file evidence, changed references, Git warnings, and the current ledger state.
4. The host interprets the evidence and may propose a replacement `/overseer.md` body.
5. The module prepares a `WriteLedger` transaction plan.
6. The owner approves the exact ledger preview through a versioned approval envelope.
7. The module commits only if snapshot, plan, approval, and before hashes still match.

An unchanged scan creates no history entry and performs no write.

### Audit

Audit follows the same lifecycle but inventories the repository under explicit limits and exclusions. It streams hashes and bounded text inspection, then returns complete, partial, or limit-exceeded coverage. A partial result can support diagnosis but cannot authorize a transaction or a repository-wide clean claim.

### Clean

1. The host submits exact remediation intents and supporting evidence.
2. The module lowers them into the closed primitive set.
3. Policy validation rejects unsupported content classes, unsafe paths, unresolved dependencies, destination conflicts, and archive violations.
4. The module returns a deterministic preview grouped into Documentation, Organize, and Archive.
5. The preview shows forced cross-group dependencies and the owner approves any dependency-closed subset of operations and groups.
6. Transaction apply reacquires the lock and revalidates the snapshot and before hashes.
7. The journal is written and synchronized before mutation.
8. Moves and archive operations run in dependency order.
9. Documentation and reference repairs follow.
10. `/overseer.md` is written last.
11. Verification checks hashes, destinations, references, archive provenance, and ledger truth.
12. The journal becomes committed only after verification.

If execution fails, rollback runs in reverse order from exact preimage bytes. Before each reverse action it verifies the expected post-operation hash. If a concurrent external edit makes rollback unsafe, Overseer never overwrites it, stops with `manual_attention`, and preserves recovery material.

## Inventory and evidence policy

The inventory records normalized relative path, entry type, size, modification metadata used only as a hint, content hash when required, Git state when available, and conservative content classification. Detector precedence and the complete content-operation matrix are defined in `policy-contract.md`.

Default exclusions include:

- `.git/` internals;
- dependency and vendor trees;
- build outputs and caches unless the session explicitly identifies one as a managed artifact;
- existing `overseer/archive/` contents during ordinary scans;
- secret-bearing paths and environment files;
- sockets, devices, and other special filesystem entries.

Git is optional evidence, not a runtime dependency. A repository without Git remains supported. Git output is never treated as approval.

Markdown reference checking supports local relative links and conservative destination resolution. It reports uncertainty instead of rewriting unfamiliar link syntax. Binary artifacts are managed by metadata, hashes, explicit relationships, and host interpretation, not by silent content extraction.

## Document policy

The module classifies targets before accepting edits:

- living context may receive an exact before-and-after replacement;
- historical records may receive a superseding pointer only when policy permits, but their historical claims are not rewritten;
- generated files, `CHANGELOG.md`, vendor content, lockfiles, secrets, source code, and business artifact contents reject content edits;
- eligible artifacts may still be moved or archived without content changes.

High-authority instruction files such as `AGENTS.md` and `CLAUDE.md` require proposal metadata naming the stale statement, contradictory repository evidence, scope, exact diff, and expected agent-behavior effect. Style-only changes fail policy review at the skill layer and are not proposed.

## Approval model

The module does not claim to authenticate a human. The host is responsible for obtaining explicit owner approval and attesting that the owner confirmed the displayed operation set. The module ensures that the approval evidence can apply only to the prepared repository state.

An approval record contains:

- protocol version and request ID;
- prepared plan digest;
- repository snapshot digest;
- approved group names;
- approved operation IDs and displayed paths;
- host-supplied approval reference;
- explicit owner-confirmation attestation;
- timestamp used for the transaction record.

There is no standing approval, wildcard approval, `--yes`, `--force`, or implicit approval from prior runs. Silence and generic continuation are not approval. A group is executable only when every transitive operation dependency is within the approved subset.

## Filesystem safety

- Require an explicit root, canonicalize it once, and retain filesystem identity from initialization.
- Accept repository-relative exact paths only.
- Reject empty targets, root targets, parent traversal, wildcard syntax, NUL bytes, and platform-reserved path forms.
- Inspect every existing path component without following a symlink for content writes.
- Move a symlink only as the link itself and only when the exact link path was approved.
- Walk from an open root descriptor and revalidate sources, destinations, parent identities, hashes, and symlink state immediately before every operation.
- Reject case-folding collisions on filesystems where they can alias.
- Use same-filesystem atomic replacement for individual document writes where supported.
- Stage document content before the first mutation.
- Never overwrite an unapproved destination.
- Never call a shell. Invoke Git with an argument vector, bounded output, timeout, and a sanitized environment.
- Perform no network access.

Portable multi-file filesystem operations are not globally atomic. Overseer therefore guarantees preflight, exact preimages, durable journaling, reversible operation records, verification, and conflict-aware recovery rather than claiming impossible atomicity. Mutation is supported only on platforms that pass the required capability probe; Windows is inspection and preview only in version 1. Full requirements are in `platform-safety.md`.

## Determinism and performance

Inventory, findings, plans, manifests, and responses use normalized path sorting and canonical JSON encoding. Concurrent reads are permitted internally, but result order never depends on completion order.

- `scan` cost is proportional to session-scoped entries, bytes inspected, and scoped references.
- `audit` cost is proportional to repository entries, streamed bytes, Git output, and references.
- planning costs `O(P log P + D)` for `P` primitives and `D` dependency edges.
- hashing is streamed and memory is bounded by inventory metadata, findings, references, and plan size.

Configurable hard limits cover file count, total inspected bytes, individual text size, Git output, execution time, finding count, and the two-hop scan closure. Hitting a hard limit produces structured incomplete coverage and prohibits mutation from that snapshot.

## Failure and recovery states

Every mutation ends in one of four states:

```text
unchanged
committed
rolled_back
manual_attention
```

An interrupted journal produces `RECOVERY_REQUIRED` and blocks new mutations. `recover verify` determines whether all intended postconditions already hold. `recover rollback` applies recorded reverse operations and exact preimages only when expected current identities and hashes still match. It never overwrites an external change.

The ledger cannot claim success before the transaction commits because it is written last. If its write or final verification fails, the prior operations are rolled back or the transaction is explicitly marked for manual attention.

## Testing strategy

Testing starts from end-user-aligned command-line scenarios using temporary fixture repositories:

- first run with no `overseer.md` remains read-only until baseline approval;
- session scan with no material change is a true no-op;
- stale `AGENTS.md` remediation shows evidence and exact diff;
- organize approval does not imply archive approval;
- archive preserves original relative paths and provenance;
- stale snapshot and changed before hashes reject commit;
- symlink escape, root target, glob, destination collision, and protected-file edits fail closed;
- injected failure after each mutation step either rolls back completely or leaves an honest recovery journal;
- crash recovery verifies or rolls back without overwriting concurrent edits;
- Git and no-Git repositories behave consistently;
- output and plan digests are deterministic across repeated runs;
- large and adversarial trees stop at configured bounds.

Unit and property tests cover path normalization, classification, canonical serialization, dependency closure, archive derivation, journal transitions, and ledger-history suppression. Tests use fault-injecting filesystem and deterministic runtime adapters. No test requires network access.

## Technical reference map

| Component | Reference | Adoption |
| --- | --- | --- |
| Skill folder and progressive disclosure | Agent Skills specification | Adopt the standard `SKILL.md`, `scripts/`, `references/`, and `assets/` layout. |
| Helper script behavior | Agent Skills script guidance | Adopt self-contained, non-interactive, structured output, dry-run defaults, and safe failure behavior. |
| Context curation | FirstMate `/stow` | Adapt inspect-then-update, most-specific ownership, pruning, compact history, and honest handoff verdicts. |
| Repository context size | Aider repository map | Adapt concise evidence selection, not its code-map implementation. |
| Canonical artifact identity | Paperless-ngx and DVC concepts | Adapt explicit identity, duplicate, supersession, and provenance concepts without their storage systems. |
| Filesystem execution | Python standard library | Implement locally with `pathlib`, `os`, `stat`, `hashlib`, `json`, `subprocess`, `tempfile`, and `shutil`. |

No prior-art code is forked.
