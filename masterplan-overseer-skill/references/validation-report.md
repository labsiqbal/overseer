# Adversarial validation report

Run on 2026-07-22 by a fresh reviewer with no conversation context.

## Findings

🔴 BLOCKER - Completeness: The structure, ownership rules, and canonical update algorithm for overseer.md are undefined. Why: Implementations cannot deterministically decide what to preserve, replace, bound, or classify as a no-op. Fix: Specify the ledger schema, stable identifiers, managed and user-owned regions, provenance fields, ordering, history limits, and byte-level replacement rules.

🔴 BLOCKER - Completeness: Repository-first reconciliation does not define authority or conflict precedence among source files, configuration, tests, documentation, generated artifacts, and host proposals. Why: The agent can confidently rewrite correct documentation from misleading or stale evidence. Fix: Define an evidence hierarchy, conflict taxonomy, confidence thresholds, ambiguity stops, and cases that always require owner-supplied resolution.

🔴 BLOCKER - Completeness: Exact approval has no protocol or trust boundary. Why: A host can accidentally or maliciously represent ordinary conversation as approval, and the module cannot prove what the owner actually approved. Fix: Define a versioned approval envelope containing operation IDs, paths, before hashes, snapshot and plan digests, selected groups, expiry, and an explicit host attestation, while documenting that identity trust remains the host's responsibility.

🔴 BLOCKER - Completeness: First-run baseline confirmation has no defined artifact, digest, transition, or persistence behavior. Why: Implementations will disagree about when mutation becomes legal, and persisting confirmation may itself violate the first-run read-only rule. Fix: Define a read-only baseline preview followed by a separately approved baseline initialization transaction and explicit initialized state.

🔴 BLOCKER - Completeness: The protected-content policy does not specify which operations are prohibited for each content class. Why: One implementation may forbid moving source while another may archive it, and business-artifact movement can conflict with the general protected-content statement. Fix: Provide a content-class by operation matrix covering inspect, hash, excerpt, rewrite, move, archive, and reference repair, including override rules.

🔴 BLOCKER - Completeness: The public request and result contracts are only named, not specified. Why: A coding agent cannot implement interoperable canonical JSON, validation, errors, previews, approvals, or recovery behavior from type names alone. Fix: Define versioned field-level schemas, tagged result variants, error codes, path encoding, timestamps, limits, and canonical JSON test vectors.

🟡 IMPROVEMENT - Completeness: Root discovery and repository boundaries are undefined for nested repositories, worktrees, monorepos, submodules, and invocation below the root. Why: The skill may inventory or mutate the wrong tree. Fix: Require an explicit canonical root or specify deterministic discovery, boundary, and nested-repository policies.

🟡 IMPROVEMENT - Completeness: Reference discovery and repair have no supported syntax or completeness contract. Why: Moves can leave broken links in Markdown, configuration, source, manifests, or case-sensitive references. Fix: Enumerate supported reference forms, classify unsupported or ambiguous references, and block moves when required repairs cannot be safely expressed.

🟡 IMPROVEMENT - Completeness: Detector behavior and configuration precedence are unspecified. Why: Generated, vendor, secret, historical, lock, source, and business-artifact classifications will vary and may overlap. Fix: Define ordered first-party detector rules, confidence and reason output, configuration overrides, overlap resolution, and fixture-based conformance tests.

🟡 IMPROVEMENT - Completeness: Acceptance criteria lack crash, concurrency, adversarial-path, encoding, and recovery scenarios. Why: A nominal implementation can satisfy feature prose while failing the safety properties that distinguish the product. Fix: Add executable scenario matrices and golden fixtures for every transaction phase and fault boundary.

🔴 BLOCKER - Consistency: The phrase "every commit" requires approved dependency-closed groups, but scan and audit ledger updates have no groups and Git commits are optional. Why: It is unclear whether the invariant applies to all mutations, clean transactions only, or version-control commits. Fix: Rename the operation to transaction apply and state the exact invariant separately for ledger-only and clean transactions.

🔴 BLOCKER - Consistency: Independently selectable clean groups conflict with dependency closure when a move requires documentation or reference repairs in another group. Why: Either the selection is not independent or an approved subset can leave the repository inconsistent. Fix: Define operation-level dependencies across groups, show forced selections before approval, and reject any selection whose transitive closure is not approved.

🔴 BLOCKER - Consistency: "Never permanent delete" conflicts with atomic replacement, temporary files, stale locks, transaction backups, and bounded metadata. Why: A literal implementation cannot clean internal artifacts, while an implicit cleanup implementation introduces an undeclared delete capability. Fix: Distinguish user-content deletion from narrowly scoped internal artifact cleanup and specify retention and safe unlink rules.

🟡 IMPROVEMENT - Consistency: A bounded repo-wide audit can become partial, while partial snapshots cannot authorize mutation. Why: Users may be offered a ledger update from an audit that is described as repo-wide but is ineligible to authorize it. Fix: Define complete, partial, and coverage-limited audit outcomes and suppress approval whenever completeness requirements are unmet.

🟡 IMPROVEMENT - Consistency: No-op scan semantics do not state whether state, lock, journal, access times, or temporary files count as writes. Why: Implementations can claim a no-op while still changing persistent project data. Fix: Define no-op as no durable namespace or content changes and require temporary artifacts to be outside the project or fully removed.

🔴 BLOCKER - Feasibility: Reverse rollback of EditLivingDocument and WriteLedger is impossible from hashes and JSON metadata alone. Why: Without Git, the old bytes needed to restore overwritten files do not exist. Fix: Add transaction-scoped preimage storage with byte hashes, permissions, atomic creation, restrictive access, lifecycle rules, and recovery verification.

🔴 BLOCKER - Feasibility: A per-root lock does not protect against external editors, Git operations, or other tools changing files between validation and mutation. Why: A plan can pass its initial hashes and still overwrite concurrent changes during a multi-step transaction. Fix: Revalidate source, destination, parent, and symlink state immediately before every operation and abort conflict-aware without overwriting any changed path.

🔴 BLOCKER - Feasibility: Portable durable transaction semantics are not defined for Windows and POSIX filesystems. Why: File replacement, directory fsync, file locking, case-only rename, open-file behavior, and crash guarantees differ materially across targets. Fix: Specify platform adapters and guarantees, use same-filesystem staging, document weaker guarantees where unavoidable, and include platform fault tests.

🟡 IMPROVEMENT - Feasibility: Archive destinations can collide when the same relative path is archived more than once per day or differs only by case or Unicode normalization. Why: A later archive may overwrite an earlier one or become unrestorable. Fix: Use transaction-qualified immutable archive paths, collision rejection, normalized comparison keys, and manifests that preserve original byte names.

🟡 IMPROVEMENT - Feasibility: Supported filesystem object types are unspecified. Why: FIFOs, sockets, device files, sparse files, hardlinks, junctions, and unreadable files can hang inspection or violate copy and rollback assumptions. Fix: Define an allowlist of regular files and directories, reject unsupported objects before planning, and preserve required metadata explicitly.

🟡 IMPROVEMENT - Feasibility: Text editing does not define encoding, newline, BOM, permissions, or executable-bit preservation. Why: A semantically correct edit can corrupt a file or create noisy full-file diffs. Fix: Require byte-preserving transforms around explicitly decoded text and verify all metadata that must survive replacement.

🟡 IMPROVEMENT - Feasibility: The optional Git adapter has no behavior for dirty worktrees, ignored files, submodules, renames, untracked files, or absent Git commands. Why: Scan coverage and before-state identity will differ unpredictably across repositories. Fix: Define Git as an evidence source only, specify fallback semantics, and publish a conformance matrix for repository states.

🟡 IMPROVEMENT - Optimization: Immutable snapshots and repeated full hashing have no streaming or resource-budget design. Why: Large repositories can exhaust memory or repeatedly reread unchanged files while still producing an unusable partial snapshot. Fix: Specify streaming inventory, bounded concurrency, stable metadata-first filtering, optional fingerprint caching, and deterministic degradation.

🟡 IMPROVEMENT - Optimization: Scan's session paths and Git delta do not include a defined dependency-expansion algorithm. Why: A supposedly lightweight scan may either miss affected references or degenerate into an audit. Fix: Define a bounded reference and ownership closure with explicit coverage reporting and escalation to audit when closure cannot be proven.

🟡 IMPROVEMENT - Optimization: The design has two adjacent runtime artifacts named overseer.md and overseer/. Why: This consumes a generic project namespace and risks collisions with existing files or directories. Fix: Reserve a less collision-prone metadata directory, define adoption and collision behavior, and make all generated paths centrally configurable only before initialization.

🔴 BLOCKER - Risk: Repository contents and documentation are untrusted prompt-injection inputs, but no isolation rule is stated. Why: A malicious file can instruct the host agent to fabricate evidence, bypass approval, or propose destructive moves. Fix: Require all repository text to be treated as inert evidence, keep safety decisions inside deterministic helpers, delimit excerpts, and never execute or follow embedded instructions.

🔴 BLOCKER - Risk: Root confinement plus preliminary symlink checks is vulnerable to time-of-check to time-of-use path replacement. Why: An attacker or concurrent process can swap a checked path or parent for a symlink or junction before mutation and escape the root. Fix: Use descriptor-relative no-follow operations where supported, revalidate every component at mutation time, reject junctions and reparse points, and fail closed on platforms without equivalent guarantees.

🔴 BLOCKER - Risk: Previews, ambiguity reports, journals, manifests, and error messages have no secret-redaction policy. Why: A protected secret may be copied into overseer.md, transaction data, terminal output, or host conversation even when source rewriting is prohibited. Fix: Define secret-safe evidence records using path, classification, hashes, and redacted metadata only, with restrictive permissions and explicit bans on secret excerpts.

🔴 BLOCKER - Risk: Rollback behavior under conflicts is not defined. Why: Restoring a preimage after a user edits a partially mutated file can destroy newer work, while refusing restoration can leave an inconsistent repository. Fix: Require post-mutation hash checks before each rollback action, preserve conflicting versions, report manual recovery steps, and never overwrite unexpected state.

🟡 IMPROVEMENT - Risk: Archive and transaction retention can indefinitely duplicate sensitive business artifacts and living-document contents. Why: "Never delete" creates an accumulating local data-retention and exposure problem. Fix: Define owner-controlled retention, encrypted-storage guidance, restrictive permissions, and an explicit separately approved purge mechanism for Overseer-owned recovery data.

🟡 IMPROVEMENT - Risk: Atomic replacement and moves do not specify permission, ownership, ACL, extended-attribute, or hardlink behavior. Why: Files can become more readable, lose security labels, or unexpectedly affect aliases outside the repository. Fix: Preserve and verify required metadata, use replace-based writes instead of in-place mutation, and reject unsafe hardlink cases.

🟡 IMPROVEMENT - Risk: Digest construction is underspecified beyond canonical JSON. Why: Path normalization, Unicode, algorithm choice, schema version, missing versus null fields, and ordered collections can produce approval mismatches or cross-platform collisions. Fix: Specify the hash algorithm, domain-separated digest envelopes, normalized relative-path representation, schema versioning, and cross-platform golden vectors.

## Disposition

All blockers were resolved before masterplan authoring:

- ledger structure, ownership, rendering, stable IDs, no-op, and bounds: `ledger-contract.md`;
- authority, conflicts, prompt isolation, content matrix, detector precedence, secrets, references, and scan closure: `policy-contract.md`;
- field-level request lifecycle, baseline transaction, approval envelope, dependency closure, result variants, and digest construction: `protocol-contract.md`;
- explicit root boundaries, capability tiers, preimages, per-operation revalidation, rollback conflicts, archive collisions, metadata, internal cleanup, Git behavior, and fault tests: `platform-safety.md`.

All improvements were adopted except two deliberate alternatives:

- The adjacent `/overseer.md` and `/overseer/` namespace remains fixed because cross-host discoverability and clear ownership are core product decisions. Initialization now detects collisions and requires explicit adoption or manual resolution.
- Overseer does not add an archive purge command. Recovery material is internally removed after verified completion, while archived project content remains owner-managed and manually deletable as originally required.

Gate B status: clear. No blocker remains open.
