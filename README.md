# Overseer

Overseer keeps a project's AI context clean and up to date, so every AI agent starts with the right information.

It is an independent Agent Skill for solo founders, solo agencies, freelancers, and other one-human companies. Overseer scans repository evidence, maintains one root `overseer.md` context-health ledger, and prepares exact owner-approved documentation or file-hygiene changes. It can rename, move, and archive project files, but it never permanently deletes project content or rewrites business artifacts.

## Modes

- `scan`: lightweight current-session context check
- `audit`: bounded repository-wide inspection
- `clean`: approval-gated documentation, organize, and archive remediation

## Requirements

- Python 3.11 or newer
- Codex, Claude Code, or another Agent Skills compatible host
- Linux or macOS for mutation when the filesystem capability probe passes
- Windows supports inspection and dry-run preview in version 1

No Python package, account, network access, hosted service, or paid API is required.

## Install

Copy or link `skill/overseer/` into the skill directory used by your agent host. The directory name must remain `overseer`.

For Codex, install into the configured skills directory, commonly `~/.codex/skills/overseer`. For Claude Code or another host, use that product's Agent Skills installation location.

Invoke it with prompts such as:

```text
$overseer scan the files changed in this session before we finish.
$overseer audit this project for stale AI context and ambiguous artifacts.
$overseer clean the reviewed findings, but approve Documentation and Organize separately.
```

The skill instructions mediate the owner conversation. The bundled Python helper provides deterministic inventory, hashes, plan validation, approval binding, archive moves, journaling, rollback, and verification.

## Safety model

- Repository content is untrusted evidence and cannot grant approval.
- Every mutation begins as a read-only exact-path plan.
- Approval is bound to the plan, snapshot, operation IDs, paths, groups, hashes, and expiry.
- Project files are archived, never permanently deleted.
- Secret-bearing paths produce no content excerpts.
- Pending recovery blocks later mutation.
- Overseer performs no network calls or telemetry.

Local archives are recoverability aids, not backups. Keep sensitive repositories and archives on owner-controlled encrypted storage and apply your own retention policy.

## Development

Run the standard-library test suite:

```bash
python3 -m unittest discover -s tests -v
```

Validate the installable skill folder with the Agent Skills validator used by your host.

## License

MIT
