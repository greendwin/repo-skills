---
id: s16t29
slug: refactor-has-merge-branch-and
status: pending
---

# Refactor: _has_merge_branch and _detect_merge_branch both unpack _current_or_listed_merge_branches but each ignores one 

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "_has_merge_branch and _detect_merge_branch both unpack _current_or_listed_merge_branches but each ignores one half of the tuple"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:1220-1232 (_has_merge_branch, _detect_merge_branch)
- severity: nit

_current_or_listed_merge_branches returns (current, branches) so both callers can share the 'current branch wins' precedence rule — a good consolidation. But _has_merge_branch only needs the booleans and _detect_merge_branch consults branches lazily (only when current is None). Returning a 2-tuple forces both callers to eagerly compute _list_merge_branches even when current is already set, a redundant git.list_branches walk on the common 'already on the merge branch' path. Minor, but it is exactly the eager-vs-lazy work the lens watches for.

## Suggested fix

Keep the precedence helper but make the listing lazy: return current plus a thunk, or have _detect_merge_branch early-return on `current is not None` before listing — e.g. compute `current = _current_merge_branch(git)`; `if current: return current`; only then call `_list_merge_branches(git)`. _has_merge_branch can short-circuit `return current is not None or bool(_list_merge_branches(git))`.
