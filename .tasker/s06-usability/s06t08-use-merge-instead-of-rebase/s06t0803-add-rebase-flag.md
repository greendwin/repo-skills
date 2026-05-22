---
id: s06t0803
slug: add-rebase-flag
status: pending
---

# Add --rebase flag

**Goal:** Add `--rebase` CLI option that preserves the old rebase behavior end-to-end.

**Decisions:** `--rebase` flag preserves old behavior — opt-in for users who want linear history.

**Key files:** `src/repo_skills/cli/_merge.py`, `tests/cli/test_merge.py`
