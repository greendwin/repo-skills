---
id: s06t0804
slug: update-continue-and-abort-to
status: pending
---

# Update --continue and --abort to handle both states

**Goal:** `_merge_continue` checks `is_merging()` in addition to `is_rebasing()`. When neither is active, defaults to merge. `_merge_abort` checks both states. Dirty repo allowed during active merge (like during rebase).

**Decisions:** `--continue`/`--abort` detect both states, `--continue` defaults to merge when no conflict state is active.

**Key files:** `src/repo_skills/cli/_merge.py`, `tests/cli/test_merge.py`
