---
id: s16t27
slug: refactor-list-merge-branches-split
status: pending
---

# Refactor: list-merge-branches + _split_merge_branch match repeated across _active_merge_branch_for and _detect_merge_bra

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "list-merge-branches + _split_merge_branch match repeated across _active_merge_branch_for and _detect_merge_branch path"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:1261-1272 (_active_merge_branch_for) and :1204-1211 (_list_merge_branches)
- severity: nit

_active_merge_branch_for iterates `_list_merge_branches(git)` and matches each via `_split_merge_branch(b) == (provider, skill)`; the same list-then-parse shape underlies the resume path. The reviewer explicitly frames this as borderline-incidental (the two callers want different things) and a watch item, not a required change — 'leaving them separate is acceptable.' Routing to delayed as a side-task seed rather than forcing a speculative helper in place, per the aggressive-delayed bias.

## Suggested fix

Optional / on rule-of-three: if a third caller appears, factor the `(provider, skill)` match predicate into a named helper `def _branch_targets(branch, provider, skill): return _split_merge_branch(branch) == (provider, skill)` and reuse it in _active_merge_branch_for. For the current two callers leaving them separate is acceptable.
