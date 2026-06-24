---
id: s16t02
slug: unify-same-source-and-cross
status: in-review
---

# Unify same-source and cross-source merge engines

Follow-up refactor from s08t36 (delayed). `_merge_start` and `_merge_retarget` in `src/repo_skills/cli/_merge.py` duplicate the entire branch-merge engine near-verbatim (~90 lines each): in-progress branch guard, `_resolve_base_commit`, branch creation, `overwrite_dir`, `no_commit` block, `commit_all`, merge/rebase/rebase_root selection, conflict-warning block. They differ only in working source (`target` vs `source`), `force=True`, the keep-source `mark_keep_source` calls, and the finalize tail.

Goal: extract one shared merge engine parameterized by `(source/target, force, keep_source, on_finalize)`; same-source path = `force=False, keep_source=False, on_finalize=_finalize`, cross-source = `force=True, keep_source=<flag>, on_finalize=<retarget finalize>`. Also route the *synchronous* retarget tail through `_finalize` instead of open-coding `checkout`/`fast_forward`/`overwrite_dir`/`delete_branch` (currently duplicated between `_merge_retarget` and `_finalize`), and consolidate the keep-source decision to one pre-dispatch point. While here, replace the hardcoded `"skill-merge/"` literals with `MERGE_BRANCH_PREFIX`.

Large/risky, touches the legacy same-source path. **Must be done test-first** against the full `tests/cli/test_merge.py` matrix (TestMerge* + TestMergeRetarget + TestMergeContinue/Abort + TestMergeKeepSourceState) — behavior must be byte-identical. Preserve the hard-won keep-source-leak fixes.
