# Verdict: do not build Overseer as a standalone control plane

Date: 2026-07-22

## Finding

The proposed standalone Overseer product rests on a false differentiation premise. Its intended audience, command surface, agent oversight, project-scoped work, dynamic operational views, approvals, and durable artifacts substantially overlap capabilities and product direction that already exist in the owner's Proxima codebase.

Proxima is already the appropriate application boundary. It owns the durable runtime concerns that a control plane needs: runner integration, sessions and runs, task and workflow execution, schedules, continuation, worktree isolation, review, authentication, multi-project state, and the Archive registry.

Building those concerns again under Overseer would create two products with competing sources of truth, duplicated reliability work, and an unclear reason for users to choose one.

## Decision

Do not produce a build package for Overseer as a standalone application. Continue investing in Proxima as the control plane.

The name and useful project-specific concept may be retained for a new, narrower skill. That skill must not own runners, global projects, scheduling, authentication, or an independent execution engine. Its corrected pitch must pass a new Phase 1 confirmation before planning continues.

## Evidence

- `references/proxima-comparison.md`
- `/home/iqbal/firstmate/projects/proxima/PRODUCT.md`
- `/home/iqbal/firstmate/projects/proxima/docs/product/vision.md`
- `/home/iqbal/firstmate/projects/proxima/docs/product/core-flows.md`
- `/home/iqbal/firstmate/projects/proxima/docs/CAPABILITIES.md`
- `/home/iqbal/firstmate/projects/proxima/docs/reference/architecture.md`
- `/home/iqbal/firstmate/projects/proxima/docs/ui-shell.md`

## Re-entry condition

Restart masterplanning with the corrected skill premise. The skill should solve a repo-local project-intelligence or artifact-presentation job that Proxima can consume, while remaining independently usable by another host agent.
