# Phase 2 quick scan - project hygiene and artifact curation

Date: 2026-07-22

## 1. Paperless-ngx

Closest pattern for turning an uncontrolled file inbox into an organized document archive.

Patterns to absorb:

- a consumption or inbox boundary for unclassified files;
- preserve the original and make derived/archive forms explicit;
- structured metadata such as title, type, correspondent, tags, created date, and archive identity;
- content-hash duplicate detection;
- configurable filename templates and a deliberate renaming operation;
- bulk review and correction after automatic classification.

Difference: Paperless-ngx is a document management application that imports files into its own storage model. Overseer must work in place across a mixed repository, including code, Markdown, images, CSV, HTML, invoices, downloads, and generated artifacts.

Primary sources:

- https://docs.paperless-ngx.com/usage/
- https://docs.paperless-ngx.com/configuration/
- https://docs.paperless-ngx.com/advanced_usage/

## 2. DVC

Closest pattern for durable artifact lineage, current versions, reproducibility, and keeping small text metadata in Git while large outputs live elsewhere.

Patterns to absorb:

- represent artifact state and lineage in versionable text metadata;
- identify outputs independently of fragile human filenames;
- relate a generated output to the inputs and process that produced it;
- retain recoverability without presenting every historical copy as current;
- determine what became stale when an upstream input changed.

Difference: DVC is optimized for data and ML pipelines. Overseer needs semantic curation for general business and creative artifacts and must not require DVC infrastructure.

Primary sources:

- https://dvc.org/doc
- https://dvc.org/blog/ml-experiment-versioning/
- https://dvc.org/blog/cloud-versioning/

## 3. Aider repository map

Closest pattern for reducing a repository into concise, useful AI context.

Patterns to absorb:

- generate a bounded map instead of dumping the full filesystem into context;
- rank important information;
- include relationships and critical facts, not only paths;
- regenerate the map as the repository changes.

Difference: Aider's map focuses on source-code symbols needed for editing. Overseer's Markdown index must cover canonical documents, artifacts, decisions, active versions, archives, ambiguity, and freshness across non-code work.

Primary source:

- https://aider.chat/docs/repomap.html

## 4. Proxima Archive and Satpam

Closest host integration patterns already present in the owner's target product.

Patterns to absorb or reuse:

- durable artifact identity, lineage, versions, approval state, and missing-file status from Archive;
- scheduled execution and owner-facing review through Proxima;
- distinction between an in-flight run watchdog and a resting-project hygiene audit.

Difference: Satpam detects alive-but-unproductive agent runs. Archive remembers produced artifacts. Neither currently performs semantic repository cleanup, canonical-file selection, document drift detection, download triage, naming repair, or clean AI-context index generation.

Local primary sources:

- `/home/iqbal/firstmate/projects/proxima/docs/CAPABILITIES.md`
- `/home/iqbal/firstmate/projects/proxima/docs/reference/architecture.md`
- `/home/iqbal/firstmate/projects/proxima/apps/api/proxima_api/satpam.py`
- `/home/iqbal/firstmate/projects/proxima/apps/api/proxima_api/artifact_registry.py`

## Provisional direction

Use an Assemble absorption level:

- Paperless-ngx consumption and metadata discipline;
- DVC lineage and upstream-staleness concepts;
- Aider's concise generated-context principle;
- Proxima scheduling, execution, approval, and artifact registry integration.

The distinct product job is semantic maintenance of a trusted Markdown context index derived from mixed project files. Overseer does not generate domain artifacts and must not expand into a general artifact-production workflow.
