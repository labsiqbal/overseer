# Phase 4 stack comparison

Date: 2026-07-22

## Constraints

- Portable Agent Skill compatible with Codex, Claude Code, and other Agent Skills clients.
- No hosted service, account, database, or network requirement.
- Semantic judgment remains with the host agent.
- Inventory, hashing, path validation, dry runs, archive moves, rollback metadata, and post-operation verification must be deterministic.
- Permanent deletion is forbidden.
- The skill and all user-facing content are English.

## Option A - Agent Skill plus Python standard-library helpers

Structure:

```text
overseer/
├── SKILL.md
├── LICENSE
├── agents/openai.yaml
├── scripts/
│   ├── inspect.py
│   ├── validate_plan.py
│   ├── apply_plan.py
│   └── validate_overseer.py
├── references/
│   ├── policies.md
│   └── schemas.md
└── assets/
    └── overseer-template.md
```

The host agent performs semantic reconciliation and produces a bounded remediation plan. Python 3 standard-library scripts provide deterministic filesystem inventory, hashes, Git evidence, Markdown-link checks, plan validation, dry-run output, path-confined moves, archive journaling, and post-operation verification. Scripts emit structured JSON and never prompt interactively.

Strengths:

- transparent and inspectable source;
- no package installation or network access;
- strong safety boundary for risky file operations;
- broadly available on coding-agent hosts;
- easy to test at behavior level;
- scripts remain optional for clients that can perform equivalent deterministic operations.

Tradeoff: requires Python 3 for the safest deterministic path. Compatibility metadata must say so plainly.

## Option B - Instructions-only Agent Skill

Structure: `SKILL.md`, references, and an `overseer.md` template only. Every host agent implements scanning, hashing, link checks, move plans, and verification with its native tools.

Strengths:

- maximum format and runtime portability;
- smallest package;
- no language dependency.

Weaknesses:

- file safety varies by host and model;
- repeated ad hoc scripts consume tokens and create inconsistent behavior;
- harder to guarantee dry runs, path confinement, idempotency, or rollback evidence;
- unacceptable reliability risk for archive moves and broad repository audits.

## Option C - Agent Skill plus Go helper binary

The skill delegates deterministic inventory and file operations to a compiled Go CLI.

Strengths:

- strong filesystem and concurrency behavior;
- predictable performance on large repositories;
- no runtime dependency after installation;
- one coherent CLI contract.

Weaknesses:

- requires per-platform binary releases or a Go toolchain;
- bundled binaries are less transparent to agents and users than source scripts;
- installation and update paths differ across clients;
- the binary becomes a second product surface that must be versioned and secured.

## Recommendation

Choose Option A. It preserves the open Agent Skills format while giving destructive-adjacent operations a deterministic, testable implementation. Python's standard library is sufficient, so the skill remains offline and dependency-free. Option C is the runner-up if real repository benchmarks later prove Python inadequate. Option B is rejected for `clean` because instructions alone cannot provide a stable safety contract across hosts.

## Primary references

- https://agentskills.io/specification
- https://agentskills.io/skill-creation/using-scripts
- https://code.claude.com/docs/en/slash-commands
- Local Codex `skill-creator` guidance at `/home/iqbal/.codex/skills/.system/skill-creator/SKILL.md`
