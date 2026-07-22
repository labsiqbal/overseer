# Ledger contract

## Ownership and markers

`/overseer.md` is UTF-8 Markdown with one Overseer-managed block:

```text
<!-- overseer:managed schema=1 -->
...managed content...
<!-- /overseer:managed -->
```

Bytes before and after the managed block are owner-owned and preserved byte for byte. A new baseline contains only the managed block and one trailing newline. After initialization, missing, nested, duplicated, or malformed markers produce `LEDGER_CONFLICT` and block ledger mutation. Overseer never guesses how to merge a damaged ledger.

The host proposes semantic entries. The deterministic module validates, normalizes, orders, renders, and replaces the complete managed block. It never appends arbitrary prose.

## Managed schema

The block has exactly these sections in this order:

```markdown
# Overseer

Project context health: CLEAN | ATTENTION | BLOCKED
Last material review: <RFC 3339 timestamp or never>
Last complete audit: <RFC 3339 timestamp or never>
Resume from: <one sentence or none>

## Canonical context

| ID | Subject | Authoritative source | Scope | Evidence | Status |
| --- | --- | --- | --- | --- | --- |

## Open findings

| ID | Kind | Subject | Evidence | Required resolution |
| --- | --- | --- | --- | --- |

## Recent material history

- <timestamp> `<event-id>`: <bounded summary>
```

Empty tables retain their headers and contain one row with `None`. Empty history contains `- None`.

## Stable identifiers

Canonical context IDs are the first 16 lowercase hexadecimal characters of:

```text
SHA-256("overseer:context:v1\0" + canonical_subject_key)
```

Finding IDs use the same construction with domain `overseer:finding:v1` and a key formed from finding kind, normalized subject path or topic, and most-specific authoritative source. Event IDs use `overseer:event:v1` plus transaction ID and plan digest.

IDs remain stable when descriptions improve. A semantic owner change intentionally creates a new context ID and retires the old entry.

## Ordering and rendering

- Canonical context sorts by normalized scope, normalized authoritative source, then ID.
- Findings sort by severity `BLOCKED`, `ATTENTION`, then by kind, normalized subject, and ID.
- History sorts newest first.
- Table cells escape pipes and collapse internal line breaks to spaces.
- Timestamps are RFC 3339 UTC with seconds precision and `Z` suffix.
- Paths use repository-relative POSIX separators.
- Rendering uses LF line endings inside the managed block regardless of surrounding owner bytes.
- The managed block always ends with exactly one LF before the closing marker.

## Status algorithm

- `BLOCKED` means at least one finding prevents a trustworthy AI handoff, including an unresolved authority conflict, damaged ledger, partial evidence used as if complete, or recovery-required transaction.
- `ATTENTION` means findings exist but the recorded canonical context remains usable.
- `CLEAN` means the inspected scope has no unresolved findings and the coverage statement is complete for the invoked mode.

A scoped scan can report `CLEAN` only for its declared session scope. It does not advance `Last complete audit`. The host must not phrase a scoped result as repository-wide cleanliness.

## No-op and history bounds

Before replacement, the module renders the proposed managed block and compares its bytes with the existing managed block. If they are identical, the result is `unchanged` and no durable project path, state, transaction, or history is modified.

History records material curation only: baseline initialization, canonical-source changes, findings opened or resolved, approved document repair, organize move, archive move, or recovery outcome. Pure scans, timestamp refreshes, reordered equivalent input, and repeated findings are not material.

History retains at most 20 entries and at most 12 KiB. When either limit is exceeded, oldest entries are removed. The entire managed block is limited to 64 KiB. If current context and open findings alone exceed the limit, preparation fails with `LEDGER_LIMIT_EXCEEDED`; it never silently drops current truth.

## State relationship

`/overseer.md` is the only prose context ledger. `/overseer/state.json` stores only protocol version, initialization state, root identity, policy digest, latest complete evidence fingerprint, finding IDs, and transaction receipt pointers. It cannot contain descriptions, copied table rows, file contents, conversation text, or a second context index.
