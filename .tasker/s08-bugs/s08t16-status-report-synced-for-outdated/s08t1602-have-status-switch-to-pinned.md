---
id: s08t1602
slug: have-status-switch-to-pinned
status: done
---

# Have status switch to pinned branch per source

## Goal

`status` calls `ensure_on_branch` per source before scanning, so skill lists reflect the pinned branch. `--sync` pull is consolidated into the same call.

## Decisions & constraints

- **Call `ensure_on_branch(git, branch, pull=sync)` per source** — switches to the pinned branch before scanning skills, consistent with how `update` and `merge` work. *Rejected: leaving `status` branch-unaware (produces wrong available/mergeable lists when source repo is on a different branch).*
- **Replaces the separate `--sync` pull loop** — the current `if sync: git.pull()` loop becomes `ensure_on_branch(git, branch, pull=sync)`. One call handles both checkout and pull.
- Requires clean repo when on wrong branch (consistent with `update`/`merge`).
- Broken sources should be skipped gracefully (already handled by `SourceBrokenError` catch in `_scan_sources`).

## Key files

- `src/repo_skills/cli/_status.py` — status command
- `tests/cli/test_status.py` — status tests

## Acceptance criteria

- `status` switches source repo to pinned branch before scanning
- `status --sync` pulls after switching
- `status` fails with error if source repo has uncommitted changes and is on wrong branch
- `status` works fine if source repo is already on pinned branch (no-op checkout)
