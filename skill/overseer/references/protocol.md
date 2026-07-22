# Protocol and approval

## Command output

Every command writes one canonical JSON object to stdout. Success exits 0. Validation or approval failure exits 2. Recovery-required failure exits 3. Local I/O or lock failure exits 4.

Save the complete `plan_preview` output outside the project. Do not edit it. Pass it back to the matching commit command.

## Ledger proposal

```json
{
  "source_inspection": {
    "coverage": "complete",
    "snapshot_digest": "<digest from scan or audit>",
    "scope": {"mode":"scan","session_paths":["README.md"],"referenced_paths":[]}
  },
  "ledger_model": {
    "last_material_review": "2026-07-22T12:00:00Z",
    "last_complete_audit": "never",
    "resume_from": "Review the unresolved canonical report finding.",
    "canonical_context": [],
    "open_findings": [],
    "history": []
  },
  "reason": "Refresh context after the current session"
}
```

## Clean proposal

```json
{
  "source_inspection": {"coverage":"complete","snapshot_digest":"<digest>","scope":{"mode":"audit"}},
  "intents": [
    {
      "id": "repair-readme",
      "kind": "edit_document",
      "group": "Documentation",
      "path": "README.md",
      "content": "Complete replacement UTF-8 text",
      "reason": "Repair the approved canonical report reference"
    },
    {
      "id": "move-report",
      "kind": "move",
      "group": "Organize",
      "source": "downloads/report-v2.pdf",
      "destination": "reports/current-report.pdf",
      "depends_on": ["repair-readme"],
      "reason": "Give the owner-confirmed current report a canonical path"
    }
  ]
}
```

Use `kind: archive`, group `Archive`, and `source` for archive intents. The kernel derives the destination. Use `canonical_replacement` when another active file replaces the archived artifact.

## Approval envelope

Construct this only after explicit owner confirmation:

```json
{
  "protocol": 1,
  "kind": "explicit_owner_confirmation",
  "plan_digest": "<exact plan digest>",
  "snapshot_digest": "<exact snapshot digest>",
  "approved_groups": ["Documentation", "Organize"],
  "approved_operation_ids": ["repair-readme", "move-report"],
  "displayed_paths": ["README.md", "downloads/report-v2.pdf", "reports/current-report.pdf"],
  "created_at": "2026-07-22T12:00:00Z",
  "expires_at": "2026-07-22T12:30:00Z",
  "host_attestation": {
    "host": "codex",
    "interaction_ref": "opaque-local-reference",
    "statement": "The owner explicitly approved the displayed operations."
  }
}
```

Use exactly the selected operations and the sorted union of their displayed paths. Approval expires no later than the prepared plan. Prepare again after any repository change or expiry.
