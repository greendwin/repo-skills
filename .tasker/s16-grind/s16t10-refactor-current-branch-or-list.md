---
id: s16t10
slug: refactor-current-branch-or-list
status: in-review
---

# Refactor: current-branch-or-list prefix check duplicated in _has_merge_branch and _detect_merge_branch

## Refactor side-task
- depth: 1
- origin: s16t03 — refactor finding "current-branch-or-list prefix check duplicated in _has_merge_branch and _detect_merge_branch"

## Goal

Apply the deferred refactoring surfaced while processing s16t03.
- location: src/repo_skills/cli/_merge.py:1194-1197 (_has_merge_branch) and 1200-1207 (_detect_merge_branch)
- severity: nit

Both helpers open with the same two-step probe: `_merge_branch_prefix(git.current_branch()) is not None` then fall back to `_list_merge_branches(git)`. This diff touched both (swapping the old `startswith(PREFIX)` for `_merge_branch_prefix(...)` and the `list_branches` glob for `_list_merge_branches`), so the parallel pair was edited in lockstep — a small signal the current-branch precedence rule lives in two places. The duplication is shallow and the two functions return different types (bool vs str), so it is incidental rather than harmful.

## Suggested fix

Optional: extract `_current_or_listed_merge_branches(git) -> tuple[str | None, list[str]]` returning the prefixed current branch (or None) and the listed branches, letting `_has_merge_branch` test `current is not None or branches` and `_detect_merge_branch` reuse `current`. Marginal benefit; acceptable to leave as-is given the differing return shapes. Nit only.
