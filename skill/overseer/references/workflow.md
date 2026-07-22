# Overseer workflow

## First run

1. Run `scan` or `audit` with an explicit absolute root.
2. Confirm that the result is `baseline_required` and inspect `details.inspection` plus `details.collisions`.
3. Stop if a collision exists. Ask the owner whether the existing namespace is an Overseer state to adopt or unrelated content to move manually.
4. Build a complete ledger model and optional policy using the template in `assets/overseer-template.md`.
5. Run `init prepare` with a proposal stored outside the project.
6. Display the complete plan, paths, hashes, groups, reasons, expiry, and plan digest.
7. Ask the owner to explicitly approve the displayed initialization plan.
8. Build the approval envelope only after that confirmation.
9. Run `init commit`, then `scan` again and verify `initialized: true`.

Initialization proposal:

```json
{
  "ledger_model": {
    "last_material_review": "2026-07-22T12:00:00Z",
    "last_complete_audit": "2026-07-22T12:00:00Z",
    "resume_from": "none",
    "canonical_context": [],
    "open_findings": [],
    "history": [{"timestamp":"2026-07-22T12:00:00Z","summary":"Initialized Overseer baseline."}]
  },
  "policy": {
    "protocol": 1,
    "exact_exclusions": [],
    "path_classes": {},
    "limits": {}
  }
}
```

## Session-end scan

1. List exact paths created, edited, moved, or referenced during the session.
2. Run `scan` with those session and reference paths.
3. Compare durable conversation decisions with the most-specific existing context owner.
4. Classify each difference as new, duplicate, superseding, obsolete, or unresolved.
5. If only the ledger changes, use `ledger prepare` and the exact approval flow.
6. If living docs or files must change, record findings and use a separate `clean` plan.
7. Re-scan affected paths and return an honest scoped handoff verdict.

## Full audit

Use `audit` for a baseline, release, migration, major refactor, or periodic maintenance. Do not prepare mutation when coverage is `partial` or `limit_exceeded`. Resolve unreadable paths, nested roots, unsupported objects, or resource bounds first.

## Clean

1. Begin from complete scan or audit evidence.
2. Draft exact intents and evidence-backed reasons.
3. Include living-document edits needed to repair every supported reference before proposing a move.
4. Run `clean prepare`.
5. Display Documentation, Organize, and Archive separately, including forced dependencies.
6. Ask which exact operations the owner approves.
7. Commit the dependency-closed approved subset.
8. Re-scan every affected source, destination, reference owner, and ledger path.

Archive is the only removal behavior. The archive destination is derived by the kernel as `overseer/archive/YYYY-MM-DD/<transaction-id>/<original-relative-path>`.
