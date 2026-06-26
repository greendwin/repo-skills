---
id: s16t19
slug: refactor-merge-py-exceeds-the
status: pending
---

# Refactor: _merge.py exceeds the 1k-line structural guideline (now 1301 lines)

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "_merge.py exceeds the 1k-line structural guideline (now 1301 lines)"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py (whole file)
- severity: minor

The lens flags files >1k lines as a structural smell. The file was already over at the base (1269) and this change grows it to 1301. It now holds branch-naming helpers, base-commit scoring/distance math, the shared branch-merge engine, start/retarget/continue/abort flows, finalize, and merge-branch detection/parse all in one module — several cohesive clusters that would read better as separate modules (e.g. a `_merge_branch.py` for the naming/parse/detect helpers, a `_merge_base.py` for `_score_commit`/`_compute_distance`/base resolution). A dedicated refactor subtask (s16t15) already exists for this; this change is a good moment since it adds to the branch-helper cluster.

## Suggested fix

Extract the branch-name cohort — MERGE_BRANCH_STEM/PREFIX/KEEP_BRANCH_PREFIX/_MERGE_PREFIXES, _merge_branch_name, _merge_branch_prefix, _list_merge_branches, _has_merge_branch, _detect_merge_branch, _parse_merge_branch, _cleanup_legacy_merge_state — into a new `src/repo_skills/cli/_merge_branch.py` and import them into `_merge.py`. This drops `_merge.py` back under 1k and groups the branch-name-as-state logic (the heart of this change) in one place.
