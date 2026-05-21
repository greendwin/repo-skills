---
id: s02t1204
slug: merge-targets-pinned-branch
status: done
---

# Merge targets pinned branch

**Goal:** Replace `git.get_main_branch()` with `resolve_branch(config, git)` in `_merge_start`, `_finalize`, and `_merge_abort`. Update tests.

**Decisions:**
- Merge uses `resolve_branch()` at all three sites (`_merge_start`, `_finalize`, `_merge_abort`)
- Auto-checkout targets pinned branch instead of main

**Key files:** `src/repo_skills/cli/_merge.py`, `tests/cli/test_merge.py`
