# Prior-art deep dive

Research date: 2026-07-22

## Confirmed product boundary

Overseer is not a central productivity application or a replacement agent runtime. It is installed inside one project as a skill, a thin local bridge, and a generated HTML dashboard. The existing host agent remains the executor. The browser provides project-specific navigation, live state, approvals, chat, and artifact inspection.

## FirstMate

Primary sources: [repository](https://github.com/kunchenguid/firstmate), [architecture](https://github.com/kunchenguid/firstmate/blob/main/docs/architecture.md)

- **Audience and core flow:** Developers talk to one first mate, which dispatches isolated crewmates, supervises them, and returns completed changes or investigation reports.
- **Product structure:** The cloned repository is an agent distribution containing instructions, skills, scripts, policies, and disk-backed state. It deliberately does not replace the host harness.
- **Useful behavior:** One human-facing liaison, durable local state, visible worker endpoints, two task shapes, explicit delivery modes, guarded approvals, restart recovery, and event-driven supervision.
- **Important wake pattern:** Actionable events are written to a durable queue before detector state advances. A watcher wakes the supervising agent only when a human-relevant event occurs. This directly addresses the missed Lavish feedback observed during this masterplan run.
- **Technology and maturity:** Predominantly shell scripts around existing harnesses and terminal session providers. The repository is MIT licensed and materially more adopted than the other open-source candidates, with roughly 1.7k stars at research time.
- **Absorb:** Adapt the durable wake queue, one-liaison supervision contract, disk-authoritative state, and recovery principles. Do not copy coding-only worktree and PR assumptions into general business workflows.

## ORCH

Primary sources: [product and documentation](https://www.orch.one/), [repository](https://github.com/oxgeneral/ORCH), [package manifest](https://github.com/oxgeneral/ORCH/blob/main/package.json)

- **Audience and core flow:** A user defines a goal, an orchestrator decomposes it into tasks, agents execute in parallel, and results move through review before completion.
- **Product structure:** Repo-local state is stored under `.orchestry/`; task state follows `todo -> in_progress -> review -> done`; the runtime supports retries, inter-agent messaging, shared context, a headless daemon, and a TUI dashboard.
- **Useful behavior:** Explicit state machine, retries with preserved logs, review and rejection, cost/status visibility, broad adapter support, and non-coding examples such as content plus engineering launch work and CSV-to-executive-report pipelines.
- **Technology and maturity:** TypeScript on Node 20+, with Commander, Ink, React, YAML, Liquid templates, Nano ID, Vitest, and tsup. Version 1.0.27 and MIT licensed. It is active but still young, with roughly 100 stars at research time.
- **Absorb:** Adapt the task lifecycle vocabulary, retry semantics, event log shape, approval gate, and adapter boundary. Do not adopt its runtime wholesale because Overseer keeps the host agent as executor.

## Canvas

Primary sources: [quickstart](https://docs.canvas.inc/quickstart), [artifacts](https://docs.canvas.inc/artifacts), [automations](https://docs.canvas.inc/automations), [skills](https://docs.canvas.inc/skills), [file system](https://docs.canvas.inc/file-system)

- **Audience and core flow:** A user describes a business outcome in chat; the agent executes the workflow; structured results appear beside the conversation and remain available for follow-up work.
- **Artifact behavior:** Tables support search, sort, filter, and CSV export. Documents render as rich Markdown. Files such as CSVs, reports, and images persist across conversations and surface as clickable cards in chat.
- **Operational behavior:** Scheduled runs retain status, duration, summary, and full conversation history. Skills are named reusable playbooks with trigger descriptions and instructions.
- **Product structure:** The documented platform is cloud-hosted and uses a persistent agent sandbox. Its implementation is proprietary.
- **Absorb:** Pattern only. Adopt first-class persistent artifacts, chat-to-artifact linking, type-specific viewers, run history, and resumable automation semantics. Do not copy code or assume cloud storage.

## OpenLoaf

Primary sources: [repository](https://github.com/OpenLoaf/OpenLoaf), [package manifest](https://github.com/OpenLoaf/OpenLoaf/blob/main/package.json)

- **Audience and core flow:** Users open project-specific windows with dedicated agents, memory, skills, files, tasks, terminal, and canvas. A secretary agent routes cross-project work.
- **Page structure:** A main command center opens project windows; each project window combines an assistant, file explorer, terminal, task board, and canvas.
- **Useful behavior:** Projects have independent context and tools, while UI modules make different work products directly inspectable.
- **Technology and maturity:** Large TypeScript monorepo with separate web, server, desktop, API, UI, database, and widget SDK packages. It uses React 19, Tailwind 4, Hono, tRPC, Prisma, Zod, Zustand, and desktop-native dependencies. AGPL-3.0 licensed and explicitly marked active development. Roughly 80 stars at research time.
- **Absorb:** Pattern only under a strict commercial-compatible posture. Borrow the project-specific module model and canvas vocabulary. Reject the central desktop, cross-project secretary, and platform-scale architecture.

## Agent Workspace

Primary sources: [product](https://agent-workspace.ai/), [repository](https://github.com/web3dev1337/agent-workspace), [package manifest](https://github.com/web3dev1337/agent-workspace/blob/main/package.json)

- **Audience and core flow:** Developers run multiple CLI agents and worktrees in one browser or desktop workspace, coordinate them from a commander, track tasks, and inspect diffs.
- **Page structure:** Worktree sidebar, central terminal grid, task board, commander surface, server windows, and a dedicated diff review console.
- **Useful behavior:** Thin local server bridges the browser to local processes and streams live state. Review remains contextual rather than forcing the user back into a terminal.
- **Technology and maturity:** Node/Express, Socket.IO, node-pty, WebSocket-style event flow, optional Tauri packaging, Jest, and Playwright. MIT licensed, version 0.1.22, and young at roughly 30 stars.
- **Absorb:** Adapt the thin bridge boundary, event streaming, and contextual review layout. Do not adopt multi-repository worktree management or terminal-grid-first UX.

## Category UX conventions to absorb

1. **One command surface:** The user describes the desired outcome to one liaison. Internal delegation remains visible but does not require chatting with every worker.
2. **Persistent work products:** Artifacts live outside the chat transcript, retain identity and history, and can be reopened later.
3. **Typed artifact viewers:** Tables, documents, images, reports, invoices, and future artifact types render through dedicated viewers and actions rather than generic file downloads.
4. **Chat-to-artifact continuity:** Agent messages contain clickable references to artifacts. Follow-up prompts operate on the selected artifact without requiring the user to restate its path.
5. **Human-attention queue:** Blocked runs, approvals, failures, and material decisions are surfaced separately from ordinary activity.
6. **Explicit lifecycle:** Every run has a current state, timestamps, event history, output pointers, and a recovery path after restart.
7. **Professional density:** This category favors data-dense operational UI, restrained visual tone, clear statuses, keyboard access, and persistent navigation over a sparse consumer-chat aesthetic.
8. **Project-specific modules:** Left navigation reflects the project's declared capabilities. Adding a module or artifact type is an extension contract, not a core-app rewrite.

## Absorption map

**Decision: Assemble (chimera).** No single product matches the confirmed boundary. Overseer will combine small permissively licensed implementation patterns with behavior learned from proprietary or copyleft products.

| Component | Reference | License | Absorb |
|---|---|---|---|
| One-liaison supervision and durable wake queue | FirstMate | MIT | Code and contract patterns, adapted to general work |
| Task lifecycle, retry, audit events, approvals | ORCH | MIT | Code and state-machine patterns, not the runtime wholesale |
| Thin browser-to-local-process bridge | Agent Workspace | MIT | Code patterns for local proxying and event streaming |
| Persistent typed artifacts and chat linking | Canvas | Proprietary | Pattern only |
| Project-specific modular workspace | OpenLoaf | AGPL-3.0 | Pattern only under strict commercial-compatible posture |

## The one difference

Unlike agent dashboards that own the runtime and span projects, Overseer lives inside one project as a skill-owned operational surface whose modules and artifact types are declared by that repository while the existing host agent remains the executor.

## Patterns deliberately rejected

- A central application that manages every project.
- A new model runtime or agent framework that competes with Codex, Claude Code, or other host agents.
- Terminal grids and git worktrees as the primary mental model.
- A cloud-only persistent sandbox.
- A fixed menu of productivity applications.
- Copying AGPL or proprietary implementation code into a potentially closed product.
