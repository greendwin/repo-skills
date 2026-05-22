---
id: s06t0802
slug: switch-mergestart-to-use-merge
status: pending
---

# Switch _merge_start to use merge by default

**Goal:** Replace `rebase`/`rebase_root` with `merge` in the happy path. Orphan branches still use `rebase_root`. Add `already_merged` param to `_finalize`. Update conflict message from "Rebase has conflicts" to "Merge has conflicts".

**Decisions:** Merge as default, orphan branches always rebase, `_finalize` receives `already_merged` flag, commit messages unchanged.

**Key files:** `src/repo_skills/cli/_merge.py`, `tests/cli/test_merge.py`
