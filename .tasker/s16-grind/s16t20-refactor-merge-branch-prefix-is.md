---
id: s16t20
slug: refactor-merge-branch-prefix-is
status: pending
---

# Refactor: _merge_branch_prefix is a string-returning function used almost everywhere as a boolean predicate

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "_merge_branch_prefix is a string-returning function used almost everywhere as a boolean predicate"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:62 (_merge_branch_prefix) and call sites 1205, 1210, 1217, 1074
- severity: minor

Of the five call sites, four only care whether the branch is a merge branch (`_merge_branch_prefix(b) is not None`) and one wants the keep-vs-plain distinction (`== MERGE_KEEP_BRANCH_PREFIX`). Returning the matched prefix string forces every boolean caller to spell out the `is not None` dance, leaking an implementation detail (which prefix matched) that those callers discard. The intent reads more directly as two named predicates.

## Suggested fix

Introduce `def _is_merge_branch(branch: str) -> bool: return branch.startswith(_MERGE_PREFIXES)` (str.startswith accepts a tuple) and `def _is_keep_branch(branch: str) -> bool: return branch.startswith(MERGE_KEEP_BRANCH_PREFIX)`. Replace the four `_merge_branch_prefix(...) is not None` sites with `_is_merge_branch(...)`, the `_finalize` line with `keep_source = _is_keep_branch(merge_branch)`, and keep prefix-stripping in `_parse_merge_branch` local (loop over `_MERGE_PREFIXES`, `removeprefix`).
