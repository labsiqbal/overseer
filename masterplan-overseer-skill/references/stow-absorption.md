# FirstMate `/stow` absorption analysis

Date: 2026-07-22

## Sources inspected

- `/home/iqbal/firstmate/.agents/skills/stow/SKILL.md`
- `/home/iqbal/firstmate/skills/stow/SKILL.md`
- `/home/iqbal/firstmate/tests/fm-stow-contract.test.sh`
- `/home/iqbal/firstmate/AGENTS.md`, sections 6 and 10

## The central mechanism

`/stow` is successful because it treats documentation as routed and curated state, not as an append-only notebook.

Its loop is:

1. inspect the current conversation and existing destinations;
2. classify durable findings by their proper owner;
3. inspect the current owner document;
4. decide whether each finding is new, duplicate, superseding, or obsolete;
5. rewrite, prune, or archive instead of appending by default;
6. expose anything that could not be captured;
7. finish with an honest safe-to-reset verdict and a resume pointer.

The internal implementation relies on FirstMate's knowledge-routing table and delivery boundaries. The public implementation makes the same idea portable by discovering established local conventions first and using a single prescribed private fallback only when no convention fits.

## What Overseer absorbs

### Inspect then update

Every Overseer run reads the repository-root `/overseer.md` plus its referenced authoritative files before writing. It must identify which existing statement is affected by new evidence. A new scan does not justify a new history line by itself.

### Most-specific ownership

The repository-root `/overseer.md` is a map and health ledger. It points to the authoritative document, file, configuration, or project instruction instead of copying durable facts into a second location.

### Replacement over accumulation

When a canonical source changes, Overseer replaces the current pointer or status and removes obsolete current-state text. It records a compact historical event only when the change is materially useful for later recovery or explanation.

### Explicit ambiguity

When two sources plausibly own the same fact, Overseer does not choose silently. It records the conflict, asks once, and remembers the chosen owner in its current routing state.

### Honest handoff state

Each run ends with one of two context outcomes:

- context clean enough for AI handoff;
- context not clean, with bounded unresolved findings and exact source pointers.

## What Overseer rejects

- FirstMate fleet-specific destinations and role boundaries;
- backlog command syntax;
- session preference capture that is unrelated to the project;
- external issue filing;
- using the skill definition itself as a memory destination;
- an unbounded append-only history.

## Resulting `overseer.md` responsibility

The note should remain compact and complementary. It should contain current context ownership, canonical pointers, active drift or ambiguity, the last material curation result, a bounded history, and the current AI-handoff verdict. It should not duplicate entire wiki notes or become another project changelog.
