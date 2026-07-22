# Overseer vs Proxima

Date: 2026-07-22

## Conclusion

The products overlap strongly in audience and desired outcome. Both help a solo operator direct AI work, inspect execution, and keep durable artifacts. Chat, agent supervision, and artifacts are therefore not meaningful differentiators by themselves.

The defensible boundary is ownership:

- **Proxima owns the operating system.** It is an installed, self-hosted, multi-project control plane with its own application shell, API, database, workers, runner integration, execution lifecycle, schedules, authentication, and durable Archive.
- **Overseer belongs to one repository.** It is a repo-local skill, thin local bridge, and generated HTML workspace. The already-active host agent remains the executor. Overseer begins with Artifacts and progressively generates a project-specific landing page and modules.

## Comparison

| Axis | Proxima | Overseer |
| --- | --- | --- |
| Installation | One durable application installed on a machine or server | One `overseer/` folder inside a project |
| Project scope | One installation connects and manages multiple projects | One instance belongs to exactly one repository |
| Runtime | Launches and supervises runners through ACP | Uses the host agent already operating in the repository |
| State | Central API, SQLite data, workers, sessions, runs, jobs, schedules, profiles | Project-owned files plus only the minimum local manifest and event bridge |
| UI | Stable product navigation and global shell | Artifact-first shell with landing page and modules proposed per project |
| Workflows | Own graph engine, jobs, schedules, review, continuation, worktrees, recovery | May show project-specific workflow views but delegates execution |
| Artifacts | Durable Archive registry with lineage, versions, approval, and permanent identity | Universal first module whose renderers and collections adapt to the repository |
| Main value | A durable cockpit that runs all of the owner's agents and projects | The exact operational interface one repository needs without adopting a new platform |

## Boundary test

Overseer remains a distinct product while it owns project-specific presentation and artifact intelligence:

- inspect one repository and propose its landing page;
- generate or revise modules as work types appear;
- render project outputs as purpose-built HTML experiences;
- expose agent state and approvals through a thin adapter;
- remain portable across Codex, Claude Code, FirstMate, and Proxima.

The following belong to Proxima and should not be rebuilt in Overseer:

- runner profiles and credentials;
- global multi-project state;
- scheduling and workflow execution engines;
- concurrency, timeout continuation, worktrees, and recovery;
- accounts, remote access, and application-wide settings.

## Recommended relationship

Overseer should be a portable project lens, not Proxima Lite. It should work without Proxima. Proxima may later detect an Overseer manifest and open its generated workspace as a richer project home or app artifact. If Overseer begins owning runners, global projects, schedules, or authentication, the feature should instead be absorbed into Proxima.

## Local evidence

- `/home/iqbal/firstmate/projects/proxima/PRODUCT.md`
- `/home/iqbal/firstmate/projects/proxima/docs/product/vision.md`
- `/home/iqbal/firstmate/projects/proxima/docs/product/core-flows.md`
- `/home/iqbal/firstmate/projects/proxima/docs/CAPABILITIES.md`
- `/home/iqbal/firstmate/projects/proxima/docs/reference/architecture.md`
- `/home/iqbal/firstmate/projects/proxima/docs/ui-shell.md`
- `/home/iqbal/_work/overseer/masterplan-overseer/references/decisions.md`
