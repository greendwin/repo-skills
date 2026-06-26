---
id: s16t21
slug: refactor-fresh-merge-block-check
status: pending
---

# Refactor: Fresh-merge block check lists+parses all merge branches instead of probing the two candidate names

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Fresh-merge block check lists+parses all merge branches instead of probing the two candidate names"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:194-198 (_run_branch_merge)
- severity: nit

The branch name for this exact (provider, skill) is already known via `_merge_branch_name`. The guard instead globs every `skill-merge*` branch, filters by prefix, and parses each back into a (provider, skill) tuple just to test equality with the current pair — reconstructing data it already has. A direct existence probe of the two candidate branch names is shorter and avoids the parse round-trip. Dups the s16t11/s16t12 re-parse finding (same in-progress block, lines 194-206); kept at nit, tracked as those tasks.

## Suggested fix

Replace the `any(_parse_merge_branch(b) == (provider.name, skill_name) for b in _list_merge_branches(git))` loop with a direct check of both candidate names, e.g. `if any(git.list_branches(_merge_branch_name(provider.name, skill_name, keep_source=k)) for k in (False, True)):` (or a small `_in_progress_branch(git, provider.name, skill_name)` helper returning the existing branch name). Already tracked as s16t11/s16t12; add a non-raising splitter so pre-validated branches are not re-parsed by the raising `_parse_merge_branch`.
