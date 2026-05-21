---
id: s02t12
slug: pinned-branch-in-source-init
status: pending
---

# Pinned branch in `source init` + remove `--any-branch`

**Goal:** `source init` captures the current branch as the "pinned branch" in `source.json`. All write operations (`merge`, `install`, `update`) target the pinned branch instead of assuming `main`. Remove `--any-branch` flag — user changes the pin explicitly instead.

**Decisions:**
- Store pinned branch in `.repo-skills/source.json` at init time (current branch).
- Provide a way to change the pin (e.g. `source set-branch` or similar).
- Remove `--any-branch` from `install` and `update`.
- Merge auto-checkouts the pinned branch on start.

**Key files:** `src/repo_skills/cli/_source.py`, `src/repo_skills/config.py`, tests
