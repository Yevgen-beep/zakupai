# STAGE7 CI Refactor Plan

## Summary
- Align all workflows to trigger only on `main` branch pushes and PRs.
- Reduce GitHub Actions surface to four core checks (lint, compose sanity, Vault health, DB migrations).
- Disable legacy Stage5/Stage6 matrices while keeping history via `if: false` flags and comments.

## Workflow Changes
- **ci.yml**
  - Replace hotfix placeholders with real commands (black/flake8, compose config, Vault health curl, Alembic migrator).
  - Add caching for migrations, artifact uploads for Vault health and DB logs.
  - Mark legacy jobs (build, pytest, smoke suites, bandit, etc.) with `if: false` for easy reactivation later.

- **ci-optimized.yml**
  - Update triggers to the new policy and mark every job as `if: false` with a note pointing to `ci.yml` as the consolidated pipeline.

- **migrations.yml**
  - Restrict to `main` branch path filters, add pip caching and artifact uploads for migration evidence.

## Open Questions / Follow-ups
1. Confirm whether Docker-in-Docker is acceptable for Vault health & migrations on shared runners.
2. Decide when to re-enable security scanning (bandit/sarif) once pipeline stability is confirmed.
3. Validate that `docker compose run --rm migrator` covers all Alembic scripts (some services may need dedicated commands).

## Suggested Next Steps
1. Apply the proposed diffs and run the workflows in a feature branch.
2. Monitor Vault health artifacts to ensure the 200/503 expectation meets prod behaviour.
3. Remove legacy workflows (`ci-optimized.yml`) once Stage7 is stable and documented.
