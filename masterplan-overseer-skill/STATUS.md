# Status: Overseer

**Masterplan version:** v1.0
**Started:** 2026-07-22
**Last updated:** 2026-07-22

**Marker convention:**

- `[ ]` pending
- `[x]` done only with evidence in the note
- `[!]` needs rework; treat as unchecked and preserve why earlier work became invalid

## Milestones

- [x] **M1 - Walking skeleton** - scaffold the MIT repository and installable skill, then prove deterministic read-only inventory through canonical JSON with no project writes.
  - Note: Implemented the source-only repository, portable skill folder, canonical JSON CLI, and explicit-root read-only inspection.
  - Evidence: `test_first_scan_is_read_only_then_initialization_commits`, `test_canonical_json_and_domain_digest_are_stable`

- [x] **M2 - Baseline and ledger slice** - implement and verify collision-safe initialization, exact approval binding, the marker-bounded ledger, policy, state, and true no-op rendering.
  - Note: Initialization now rejects both pre-existing namespace paths and prepare-to-commit namespace races.
  - Evidence: `test_existing_overseer_namespace_blocks_initialization`, `test_existing_overseer_directory_blocks_initialization`, `test_namespace_race_blocks_initialization_commit`, `test_repeat_ledger_model_is_true_noop`

- [x] **M3 - Scan and audit evidence slice** - implement streaming inventory, classification, optional Git evidence, Markdown closure, coverage states, and stable findings.
  - Note: Implemented bounded filesystem inventory, deterministic hashes, optional local Git evidence, Markdown closure, classifications, and secret-safe evidence.
  - Evidence: `test_secret_evidence_is_redacted`, `test_git_evidence_redacts_secret_paths`, installed `scan` and `audit` smoke coverage

- [x] **M4 - Clean planning and approval slice** - implement closed-primitive dry runs, policy validation, grouped dependencies, canonical digests, expiry, and exact approval envelopes.
  - Note: Plans use a closed primitive set and bind approvals to exact operations, groups, paths, snapshot, digest, and expiry.
  - Evidence: `test_dependency_closed_approval_is_enforced`, `test_approval_displayed_paths_are_exact`, `test_forged_or_stale_inspection_receipt_cannot_prepare`

- [x] **M5 - Documentation transaction slice** - implement exact text replacement, metadata preservation, preimages, durable journal, revalidation, verification, and rollback.
  - Note: UTF-8, BOM, line-ending, and mode-aware document replacement runs through atomic writes, preimages, durable journals, postcondition verification, and conflict-aware rollback.
  - Evidence: `test_clean_repairs_reference_then_moves_exact_file`, `test_stale_before_hash_rejects_without_overwrite`, `test_failure_after_first_write_restores_exact_preimage`

- [x] **M6 - Organize, archive, and reference slice** - implement exact moves, supported Markdown repairs, collision-safe archive manifests, archive-only removal, and post-move verification.
  - Note: Exact moves require supported reference repair dependencies. Archive moves preserve original relative paths and write provenance manifests. External symlinks fail closed.
  - Evidence: `test_clean_repairs_reference_then_moves_exact_file`, `test_archive_preserves_original_path_and_manifest`, `test_source_code_move_and_symlink_escape_fail_closed`

- [x] **M7 - Recovery and platform hardening slice** - implement capability probes, no-follow mutation, recovery commands, secret-safe evidence, internal cleanup, and adversarial fault matrices.
  - Note: Linux mutation passed the capability probe and E2E suite. Non-POSIX mutation fails closed. Native macOS and Windows hosts were not available in this workspace.
  - Evidence: `test_non_posix_platform_is_preview_only`, `test_explicit_recovery_rolls_back_interrupted_journal`, `test_explicit_recovery_verifies_fully_applied_journal`, installed capability smoke

- [x] **M8 - Skill packaging and host smoke slice** - complete concise skill instructions, references, assets, metadata, README, install guidance, validation, and locally available host smoke tests.
  - Note: The skill is linked at `~/.codex/skills/overseer`, validates through the Agent Skills validator, and executes from the installed path.
  - Evidence: `quick_validate.py` returned `Skill is valid!`; installed `capability` smoke returned `mutation_supported: true`

- [ ] **M9 - Full QA pass** - verify every masterplan acceptance criterion end to end and run unit, golden-vector, E2E, large-tree, concurrency, fault-boundary, recovery, and package checks.
  - Note: The current Linux gate passes 25 tests and package validation. Native platform matrices, large-tree performance, lock contention, and every-boundary crash injection remain release-hardening work.
  - Evidence: `python3 -m unittest discover -s tests -v` passed 25 tests; forward test on the ambiguous-artifact fixture stopped safely without project writes

## Blockers

None.
