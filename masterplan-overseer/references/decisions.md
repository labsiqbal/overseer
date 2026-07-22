## Phase 1 - Pitch (confirmed 2026-07-22)

Overseer is a repo-local AI operations control plane for solo founders, one-human companies, solo agencies, and freelancers. It lives as an `overseer/` folder inside each project. The user opens that project's web workspace and uses the right-side chat to command and guide agents through business and technical work. A modular left navigation reflects the needs of that project, while the main workspace shows execution state, approvals, and interactive artifacts such as reports, tables and CSVs, invoices, documents, images, and new artifact types added as the project evolves. The core action is to ask agents to perform work, oversee their execution, and inspect or approve the resulting artifacts from one project cockpit.

### Confirmed boundaries

- One Overseer instance belongs to one project or repository.
- The primary user is a solo operator: solo founder, one-human company, solo agency, or freelancer.
- Overseer orchestrates broad business and technical work, not coding alone.
- Chat is the command surface; the center workspace is the operational and artifact surface.
- Navigation modules and artifact types are extensible per project.

## Phase 2 - Absorption map

**Absorption level:** Assemble (chimera).

No existing product matches the confirmed repo-local skill boundary. Overseer will adapt FirstMate's one-liaison supervision and durable wake principles, ORCH's explicit task lifecycle and approval semantics, and Agent Workspace's thin local bridge patterns. It will learn persistent typed-artifact behavior from Canvas and project-specific modular workspace conventions from OpenLoaf without copying proprietary or AGPL implementation code.

**The one difference:** Unlike agent dashboards that own the runtime and span projects, Overseer lives inside one project as a skill-owned operational surface whose modules and artifact types are declared by that repository while the existing host agent remains the executor.

**Confirmed direction:** Repo-local skill plus a thin bundled local bridge and generated HTML dashboard. The host coding agent remains the runtime.

## Phase 3 - Product interrogation

### First-user hierarchy

- **Target umbrella:** one-human companies that may combine owned products with client work.
- **V1 beachhead:** solo agencies and freelancers managing active client projects.
- **Strong subset:** technical freelancers already comfortable working with coding or general-purpose AI agents.
- **Secondary compatibility:** solo founders running only their own product should be supported by the underlying project model, but they are not the initial positioning focus.

This hierarchy keeps the product extensible while giving the first release a concrete operating environment with recurring work, approvals, reports, documents, tabular data, and commercial artifacts.

### Current workaround and migration story

The first users already ask AI agents to perform work, but outputs and context become fragmented across repository folders, Markdown files, spreadsheets, browser tabs, and chat history. Overseer must organize this existing workflow in place. Adoption must not require replacing the user's preferred host agent, moving the project into a central service, or performing a large content migration.

### Core feature and progressive workspace model

The v1 core is an **artifact-first workspace that progressively adapts to each project**, not a fixed collection of business features or one prescribed execution workflow.

- A new Overseer installation begins with a minimal usable shell and an Artifacts module.
- Overseer learns enough about the repository and the user's intended work to propose or ask for the appropriate landing page and navigation modules.
- Additional modules and artifact experiences are created on demand as project needs emerge.
- Reports, invoices, CSV tools, document generation, image generation, and execution views are module examples, not universally required built-ins.
- Dynamic modules are therefore a core product capability. A visual no-code page builder is not implied and is not required for v1.

The task lifecycle remains important when agent work is being supervised, but the UI must not force every project into that workflow before it is needed.

### First-run experience

On first run, Overseer inspects the repository, existing artifacts, and available project context. It then proposes a project-specific landing page and initial module set for user confirmation before generating them. The user can revise the proposal, and future modules continue to be added on demand. Inspection may inform the proposal, but it must not silently commit the project to an inferred workspace structure.

## Superseding decision - standalone product stopped 2026-07-22

Read-only inspection of the owner's existing Proxima product showed that the proposed standalone Overseer control plane duplicates Proxima's established product boundary: a self-hosted solo-operator cockpit with chat, project context, agent execution, tasks, workflows, approvals, schedules, and durable artifacts.

The standalone Overseer application is therefore stopped rather than built as a second competing control plane. The useful remaining idea will be reframed as a narrowly bounded skill that complements Proxima and can remain portable across host agents. This decision supersedes the earlier Assemble absorption map and Phase 3 application-scope decisions. The investigation is preserved in `VERDICT.md` and `references/proxima-comparison.md`.
