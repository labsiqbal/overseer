# Recovery

New mutation is blocked while a transaction journal is unresolved.

## Verify

Run verification when a process stopped after changes may already have completed:

```bash
python3 <skill-dir>/scripts/overseer.py recover verify \
  --root /absolute/project \
  --transaction <transaction-id>
```

Verification marks the transaction committed only when every selected operation has the expected postcondition.

## Roll back

Run rollback when verification shows incomplete application:

```bash
python3 <skill-dir>/scripts/overseer.py recover rollback \
  --root /absolute/project \
  --transaction <transaction-id>
```

Rollback checks the current post-operation identity and hash before every reverse action. It restores exact preimages only when no external actor changed the path. It never overwrites unexpected state.

## Manual attention

If recovery returns `ROLLBACK_CONFLICT` or `manual_attention`:

1. Stop all Overseer mutation.
2. Preserve `overseer/transactions/<transaction-id>/`.
3. Compare the journal's expected before and after hashes with current files.
4. Keep every externally changed version. Never force-copy a preimage over newer work.
5. Ask the owner which version is canonical.
6. Repair manually, then run `recover verify` again if the plan postconditions now hold.

Transaction preimages are owner-only and remain only while recovery is unresolved. Successful completion removes preimage and staging bytes but retains a compact journal receipt.
