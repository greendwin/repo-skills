---
id: s16t30
slug: refactor-eager-branch-listing-regresses
status: pending
---

# Refactor: Eager branch listing regresses the current-branch fast path

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Eager branch listing regresses the current-branch fast path"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:1211-1227 (_current_or_listed_merge_branches, used by _has_merge_branch / _detect_merge_branch)
- severity: minor

The pre-refactor _has_merge_branch and _detect_merge_branch short-circuited on the current-branch prefix check and only called _list_merge_branches when the current branch was NOT a merge branch. The extracted helper now unconditionally calls _list_merge_branches (which shells out to `git branch --list` in git_real.py:262), so the common case where the process is already sitting on the merge branch now pays an extra git subprocess for a result that is discarded. The DRY consolidation is desirable but it converted a lazy computation into an eager one.

## Suggested fix

Keep the consolidation but defer the list. Return the current-prefixed branch plus a thunk/lazily-evaluated list, e.g. have the helper return only `current: str | None` and let each caller call `_list_merge_branches(git)` itself when `current is None`; or pass a `list_fn` callback. Concretely, revert _detect_merge_branch/_has_merge_branch to compute `current` via a tiny `_current_merge_branch(git)` helper (prefix check only) and call `_list_merge_branches` only in the `current is None` arm, preserving the short-circuit.
