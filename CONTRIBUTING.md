# Contributing

Keep the external skill and protocol interfaces small. Put safety policy, path validation, journaling, and verification in the deterministic kernel rather than duplicating them in host instructions.

Every behavior change requires an end-user-aligned command-line reproduction and regression test. Safety changes also require adversarial path, concurrency, rollback, and no-op coverage where applicable.

Use only the Python standard library at runtime. Do not add network calls, telemetry, permanent project-file deletion, shell-string execution, or standing approval.

Run the complete test suite and skill validator before proposing a change. Never manually edit generated files or `CHANGELOG.md`.
