# MAP · overseer

## What

Agent skill + Python helper that keeps project AI context and file hygiene clean via a root `overseer.md` ledger (scan / audit / clean).

## Open first

| Need | Open |
|---|---|
| Skill procedure | [skill/overseer/SKILL.md](skill/overseer/SKILL.md) |
| Python CLI / engine | [skill/overseer/scripts/overseer.py](skill/overseer/scripts/overseer.py) |
| Overview + safety model | [README.md](README.md) |
| Project rules | [AGENTS.md](AGENTS.md) |
| Tests | [tests/](tests/) |

## Layout

```text
skill/overseer/                 Installable skill (dir name must stay `overseer`)
  SKILL.md                      Modes, owner conversation, safety
  scripts/                      overseer.py + overseer_core/
  references/                   policy, protocol, workflow, recovery
  assets/                       overseer-template.md
  agents/                       openai.yaml
masterplan-overseer/            Design package for the tool itself
masterplan-overseer-skill/      Design package for the skill surface
tests/                          stdlib unittest suite
```

## Edges

- Install target is `skill/overseer/`; this repo is the skill source, not a consumer ledger host.
- Mutations are plan + approval bound; archives never permanent deletes; no network/telemetry.
- Run tests: `python3 -m unittest discover -s tests -v`.

## Ignore by default

- `.git/`, `tests/fixtures/`, `tests/__pycache__/`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`
