# Platform and transaction safety

## Support tiers

- Inspection and clean preview support Python 3.11 or newer on Linux, macOS, and Windows.
- Mutation support requires a capability probe for descriptor-relative, no-follow filesystem operations, same-filesystem staging, reliable advisory locking, and atomic file replacement. Version 1 targets Linux and macOS environments that pass this probe.
- Windows is inspection and preview only in version 1. Clean commit and ledger commit fail with `UNSAFE_PLATFORM` until a native reparse-point-safe adapter and Windows fault suite are implemented.

The product fails closed instead of claiming portable atomicity it cannot provide.

## Root and repository boundaries

Every request supplies an explicit absolute root. The module resolves it once, records its filesystem identity during initialization, and requires later requests to match. It never climbs parent directories automatically.

Nested Git repositories, worktrees, and submodules are separate boundaries. Inventory records them but does not traverse them unless each is separately initialized as an Overseer root. Symlinks or junctions to content outside the root are never traversed. A monorepo is one root only when the owner initializes its top-level directory explicitly.

If `/overseer.md` or `/overseer/` already exists before initialization, baseline inspection reports the collision. The owner may adopt a valid existing Overseer state or move the conflicting item manually. Overseer never silently takes over or chooses another namespace. The fixed namespace is deliberate for cross-host discoverability.

## Supported filesystem objects

Regular files, directories, and symbolic links moved as links are supported. Content edits support regular files with one hard link only.

FIFOs, sockets, devices, mount points, junctions, reparse points, unreadable entries, and files with unsafe aliasing are classified but rejected from plans. Sparse regular files may be moved without copying but are not staged as editable text. Hard-linked content edits and archive operations are rejected because they can alter or duplicate an alias outside the understood path set.

## Path and time-of-check safety

On supported POSIX systems, mutation walks from an open root directory descriptor, opens every directory component with no-follow semantics, compares device and inode identity with the prepared snapshot, and performs descriptor-relative rename or replacement. It revalidates the source, destination, destination parent, object type, symlink status, and expected hash immediately before every operation.

If any identity or hash changed, the transaction stops before that operation and enters conflict-aware rollback. The implementation never relies only on a preliminary string path or `resolve()` check. Unsupported kernel or filesystem behavior fails the capability probe.

## Transaction layout

```text
overseer/transactions/<transaction-id>/
  journal.json
  preimages/<operation-id>.bin
  staged/<operation-id>.bin
```

The transaction directory and files are created with owner-only permissions before mutation. The journal records every expected before and after hash, reverse operation, metadata expectation, and phase transition. It is synchronized before the first project mutation.

Document, ledger, and policy edits store exact preimage bytes before replacement, plus mode, ownership identity, newline and encoding observation, timestamps required for rollback, and extended attributes when supported. Preimages make rollback independent of Git.

Text edits accept UTF-8, UTF-8 with BOM, and ASCII-compatible UTF-8 content only. Unsupported encodings fail closed. The host supplies a complete proposed byte representation; the helper does not perform lossy transcoding. It preserves BOM choice, line-ending style unless the exact preview changes it, executable and permission bits, and supported extended attributes. Content edit is rejected when ownership cannot remain unchanged, ACL or security metadata cannot be preserved, or the file has multiple hard links.

## Operation order and rollback

Preparation builds cross-group operation dependencies. The preview shows required groups before approval. Execution order follows dependencies, with deterministic path and operation ID tie-breakers.

Before each rollback action, the module checks that the current path has the exact post-operation identity and hash recorded in the journal. If it matches, the reverse operation is safe. If it does not, Overseer does not overwrite it. It preserves transaction material, records `ROLLBACK_CONFLICT`, reports the expected and observed redacted identities, and provides manual recovery steps.

Conflicting versions are never silently discarded. A transaction is `committed` only after all postconditions verify, `rolled_back` only after every reverse postcondition verifies, and `manual_attention` otherwise.

## Archive identity and collisions

Archive destinations are immutable and transaction-qualified:

```text
overseer/archive/YYYY-MM-DD/<transaction-id>/<original-relative-path>
```

This retains the original relative path while preventing same-day collisions. Preparation rejects any existing destination, case-fold equivalent, or Unicode-normalization equivalent. The manifest stores display path, exact protocol path, original hash, metadata, reason, canonical replacement, approval digest, and transaction ID. Existing archive contents are never overwritten or reorganized by routine runs.

## Internal cleanup versus user content

The no-delete promise applies to project and user content. The deterministic kernel has a narrowly scoped internal unlink capability limited to its own transaction staging, preimages, temporary files, compact receipts, and locks after verified completion.

- Successful transaction preimages and staged bytes are removed immediately after the committed receipt is durable.
- Recovery-required material remains until verify or rollback resolves it.
- Receipts contain no preimage content and retain the latest 20 material transactions.
- Compacting old receipts may unlink only paths proven to be internal receipts beneath the opened transaction root.
- Archived project files are never purged by Overseer. The owner may manually delete them later.

Read-only scan and audit create no durable project paths. Any temporary inspection data lives outside the project and is removed before returning. A no-op means no project namespace, content, state, journal, or ledger change.

## Git behavior

Git is bounded local evidence only. The adapter supports tracked, modified, renamed, deleted, untracked, and ignored classification without changing the index or worktree. Submodules remain boundaries. Dirty state is valid evidence, not an error. An absent Git command or non-Git root selects the no-Git adapter and cannot weaken filesystem hashes or approval binding.

No Git command uses a shell. Argument vectors, timeouts, bounded output, and a sanitized environment are mandatory.

## Required fault testing

The test suite injects failure before and after every journal transition and filesystem primitive. It covers concurrent external edits, parent replacement, symlink swap, case-only paths, decomposed Unicode, archive collisions, disk-full writes, permission loss, process interruption, stale locks, unreadable entries, unsupported objects, and recovery replay. Supported mutation platforms must pass their native filesystem matrix before release.
