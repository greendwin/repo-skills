---
id: s16t13
slug: refactor-current-branch-or-list
status: in-progress
---

# Refactor: current-branch-or-list precedence probe duplicated across _has_merge_branch and _detect_merge_branch

## Refactor side-task
- depth: 2
- origin: s16t08 — refactor finding "current-branch-or-list precedence probe duplicated across _has_merge_branch and _detect_merge_branch"

## Goal

Apply the deferred refactoring surfaced while processing s16t08.
- location: src/repo_skills/cli/_merge.py:1205-1218 (_has_merge_branch, _detect_merge_branch)
- severity: nit

Both helpers open with the identical two-step probe: `_merge_branch_prefix(git.current_branch()) is not None`, then fall back to `_list_merge_branches(git)`. The diff edited both in lockstep (swapping `startswith(PREFIX)` for `_merge_branch_prefix` and the raw glob for `_list_merge_branches`), confirming the current-branch precedence rule now lives in two places and changes must touch both. The functions return different types (bool vs str), so the duplication is shallow rather than harmful — but the parallel edit is a signal worth consolidating.

## Suggested fix

Extract `def _current_or_listed_merge_branches(git: GitRepo) -> tuple[str | None, list[str]]` returning the prefixed current branch (or None) and the listed branches. `_has_merge_branch` becomes `current, branches = _current_or_listed_merge_branches(git); return current is not None or bool(branches)`; `_detect_merge_branch` reuses `current` for its precedence return and `branches` for the single/multiple cases. Marginal benefit given the differing return shapes; acceptable to leave as-is.
