---
id: s16t33
slug: refactor-active-merge-branch-for
status: pending
---

# Refactor: _active_merge_branch_for returns str | None but the sole caller only tests `is not None`

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "_active_merge_branch_for returns str | none but the sole caller only tests `is not none`"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:255 (_active_merge_branch_for); caller at :195 (_run_branch_merge)
- severity: nit

The helper computes and returns the matching branch name, but its only use is a boolean presence check (`if _active_merge_branch_for(...) is not None`). The branch string is never consumed, so the richer return type advertises a contract the code does not use, and a reader must look at the body to learn the value is discarded. A presence predicate states the intent (`does any in-progress merge already target this skill`) directly. If a future caller genuinely needs the branch name, widen it back then.

## Suggested fix

Rename to a predicate returning bool, e.g. `def _has_active_merge_for(git, provider_name, skill_name) -> bool: return any(_split_merge_branch(b) == (provider_name, skill_name) for b in _list_merge_branches(git))`, and call `if _has_active_merge_for(git, provider.name, skill_name):` at :195. Drops the unused return value and the `next(..., None)` scaffolding.
