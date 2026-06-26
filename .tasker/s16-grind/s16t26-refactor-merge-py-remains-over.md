---
id: s16t26
slug: refactor-merge-py-remains-over
status: pending
---

# Refactor: _merge.py remains over 1000 lines after the refactor

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "_merge.py remains over 1000 lines after the refactor"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py (1322 lines)
- severity: major

Verified at 1322 lines. The thermo-nuclear lens flags files >1k lines as a structural smell, and this is the named subject of an open refactor task (s16t15). Extracting the merge-branch-name vocabulary into a sibling module creates a NEW module, moves ~8 symbols, and rewires imports back into _merge.py — large structural work with blast radius beyond a local in-place collapse, and it has its own task home. Per the aggressive bias toward delayed, route this as a side-task seed rather than forcing it into the current slice.

## Suggested fix

Extract the merge-branch-name concern into a sibling module, e.g. `src/repo_skills/cli/_merge_branch.py`, holding MERGE_BRANCH_STEM/PREFIX/KEEP_PREFIX/_MERGE_PREFIXES, _merge_branch_name, _merge_branch_prefix, _split_merge_branch, _parse_merge_branch, _list_merge_branches, _current_or_listed_merge_branches, and _detect_merge_branch; import them back into _merge.py. Drops _merge.py below the 1k threshold and isolates an independently testable unit. Track under s16t15.
