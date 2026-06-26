---
id: s16t37
slug: refactor-eager-git-branch-listing
status: pending
---

# Refactor: Eager git branch listing regresses the current-branch fast path

## Refactor side-task
- depth: 2
- origin: s16t10 — refactor finding "Eager git branch listing regresses the current-branch fast path"

## Goal

Apply the deferred refactoring surfaced while processing s16t10.
- location: src/repo_skills/cli/_merge.py:1211-1227 (_current_or_listed_merge_branches, via _has_merge_branch / _detect_merge_branch)
- severity: minor

Pre-refactor _has_merge_branch and _detect_merge_branch short-circuited on the current-branch prefix check (`git branch --show-current`) and only shelled out to `git branch --list` when the current branch was NOT a merge branch. The extracted _current_or_listed_merge_branches now unconditionally calls _list_merge_branches, which spawns a `git branch --list` subprocess. In the common deferred-resume case the process is already on the merge branch, so the listing is computed and discarded; worse, _has_merge_branch runs once per registered source inside _detect_merge_repo's loop, paying the wasted subprocess N times per --continue/--abort. A lazy computation was converted to an eager one. Dedup: merges the second performance finding at :1254 reporting the same lost short-circuit on _has_merge_branch. Already tracked as pending task s16t30 — route to that task, do not apply in this slice.

## Suggested fix

Preserve the short-circuit while keeping the DRY consolidation: extract a prefix-only helper `_current_merge_branch(git) -> str | None`. In _has_merge_branch: `return _current_merge_branch(git) is not None or bool(_list_merge_branches(git))`. In _detect_merge_branch: compute `current = _current_merge_branch(git)`, return it if not None, and only call `_list_merge_branches(git)` in the `current is None` arm. (Pending task s16t30.)
