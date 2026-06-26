---
id: s16t11
slug: refactor-in-progress-block-check
status: in-review
---

# Refactor: In-progress block check re-parses branches that _list_merge_branches already validated

## Refactor side-task
- depth: 1
- origin: s16t03 — refactor finding "In-progress block check re-parses branches that _list_merge_branches already validated"

## Goal

Apply the deferred refactoring surfaced while processing s16t03.
- location: src/repo_skills/cli/_merge.py:186-189 (_run_branch_merge)
- severity: nit

_list_merge_branches already filters to branches with a valid merge prefix, yet the block check feeds each through _parse_merge_branch — which re-derives the prefix and can raise AppError on a malformed name. The raise path is dead here (inputs are pre-validated), so the call is doing prefix work twice and carrying an unreachable error branch. A small dedicated splitter (or having _list_merge_branches return parsed (provider, skill) tuples) makes the intent — 'does any in-progress merge target this exact skill' — read directly without the redundant re-validation.

## Suggested fix

Either have _list_merge_branches yield parsed identities, e.g. `def _iter_merge_branch_ids(git) -> Iterable[tuple[str, str]]: return (_split_merge_branch(b) for b in git.list_branches(f"{MERGE_BRANCH_STEM}*") if _merge_branch_prefix(b))`, then `if any(ident == (provider.name, skill_name) for ident in _iter_merge_branch_ids(git))`; or extract a non-raising `_split_merge_branch(branch) -> tuple[str, str] | None` used by both _parse_merge_branch and this check, so the block test never relies on the raising parser.
