---
id: s16t12
slug: refactor-in-progress-block-check
status: in-progress
---

# Refactor: In-progress block check routes pre-validated branches through the raising parser

## Refactor side-task
- depth: 2
- origin: s16t08 — refactor finding "In-progress block check routes pre-validated branches through the raising parser"

## Goal

Apply the deferred refactoring surfaced while processing s16t08.
- location: src/repo_skills/cli/_merge.py:195-198 (_run_branch_merge)
- severity: nit

The block check does `any(_parse_merge_branch(b) == (provider.name, skill_name) for b in _list_merge_branches(git))`. `_list_merge_branches` already filters to branches with a valid merge prefix, so `_parse_merge_branch` re-derives the prefix (work done twice) and its `raise AppError("Invalid merge branch")` path is unreachable for these inputs. The block test's intent — 'does any in-progress merge already target this exact skill' — reads obliquely through a parser whose failure mode cannot fire here. This is exactly the structural smell s16t11 routed for follow-up, and it is materialized in the committed diff.

## Suggested fix

Extract a non-raising splitter `def _split_merge_branch(branch: str) -> tuple[str, str] | None` (returns None on prefix-miss / missing slash), have `_parse_merge_branch` call it and raise on None, and have `_list_merge_branches` expose parsed identities, e.g. `def _iter_merge_branch_ids(git) -> Iterable[tuple[str, str]]: return (ident for b in git.list_branches(f'{MERGE_BRANCH_STEM}*') if (ident := _split_merge_branch(b)) is not None)`. Then the block check becomes `if any(ident == (provider.name, skill_name) for ident in _iter_merge_branch_ids(git))`, dropping the redundant re-validation and the dead raise.
