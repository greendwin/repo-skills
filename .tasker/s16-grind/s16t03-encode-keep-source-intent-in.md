---
id: s16t03
slug: encode-keep-source-intent-in
status: in-review
---

# Encode keep-source intent in the merge branch name

Follow-up refactor from s08t36 (delayed). Today a deferred `--keep-source` cross-source merge persists its intent in `src/repo_skills/config/_merge_state.py` (a branch-keyed set in `merge-state.json`), read back in `_finalize` and gated by the delicate `is_same_source` check, with cleanup at multiple sites (fresh retarget, conflict, continue, abort).

Goal: replace the persisted-set channel by encoding keep-source intent in the merge branch *name* (e.g. a `skill-merge-keep/<provider>/<skill>` prefix or a `keep/` infix). `_finalize`/`_detect_merge_repo`/`_detect_merge_branch`/`_merge_abort` then derive intent purely from the resumed branch name. Benefits: deletes `_merge_state.py` + `mark/clear/load_keep_source`, removes the `is_same_source` exclusion gate and ~4 stale-intent cleanup sites, and makes intent self-invalidate with the branch.

Large/risky — this is exactly the code path where the keep-source-leak bug class lived. **Must be done test-first**: rewrite `TestMergeKeepSourceState` (and the relevant `TestMergeRetarget` cases) to assert on branch names rather than the JSON set, and keep every keep-source/leak regression test green. Strictly a quality improvement, not a correctness fix — the current approach is correct and tested.
