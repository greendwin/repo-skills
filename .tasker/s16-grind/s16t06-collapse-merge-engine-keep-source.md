---
id: s16t06
slug: collapse-merge-engine-keep-source
status: pending
---

# Collapse merge-engine keep-source flags to one (contested)

Follow-up refactor from s08t40 (delayed). `_run_branch_merge` in `src/repo_skills/cli/_merge.py` carries two booleans, `keep_source` and `record_keep_source`. Only two combos occur: same-source passes `(False, False)`; retarget passes `(<user>, True)`. The thermo-nuclear lens proposes collapsing to one flag and running `clear_keep_source(branch_name)` UNCONDITIONALLY (out of the `if record_keep_source` guard) for every fresh merge, arguing it's correct defensiveness.

CONTESTED — handle with care. The general code-review lens in s08t40 explicitly REFUTED collapsing to `keep_source` alone: `record_keep_source` is load-bearing at the pre-create `clear_keep_source` — that clear must fire for a *non*-keep-source retarget (`record_keep_source=True, keep_source=False`) so a fresh retarget can't inherit stale intent from an abandoned run. The thermo counter (clear unconditionally for same-source too) MIGHT resolve this but changes the keep-source-leak invariant the parent task was mandated to preserve.

Goal: if pursued, prove via test-first that running `clear_keep_source` unconditionally is behavior-preserving for the same-source path (currently same-source relies on `_finalize`'s `is_same_source` exclusion, NOT an engine-level clear). Add regression tests for the same-source-stale-intent case BEFORE changing the gating. Full `tests/cli/test_merge.py` matrix (esp. TestMergeKeepSourceState) must stay green and byte-identical. If the unconditional clear can't be proven safe, drop this and keep the dual flag.
