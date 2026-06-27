---
id: s16t15
slug: refactor-merge-py-exceeds-the
status: in-progress
---

# Refactor: _merge.py exceeds the 1k-line module threshold

## Refactor side-task
- depth: 2
- origin: s16t08 — refactor finding "_merge.py exceeds the 1k-line module threshold"

## Goal

Apply the deferred refactoring surfaced while processing s16t08.
- location: src/repo_skills/cli/_merge.py (1297 lines)
- severity: nit

The lens flags files over ~1k lines as a structural smell, and _merge.py is at 1297. This is pre-existing and the change under review actually reduces surface area (it deletes the entire config/_merge_state.py module and three exported functions, replacing persisted state with branch-name encoding), so the diff trends the right way. Noted for awareness, not as a regression introduced here.

## Suggested fix

No action required for this change. If the module keeps growing, split cohesive clusters into submodules — e.g. branch-name helpers (_merge_branch_name/_merge_branch_prefix/_parse_merge_branch/_list_merge_branches/_detect_merge_branch) into a `_merge_branches.py`, and the base-commit scoring (_score_commit/_compute_distance) into a `_merge_base.py` — leaving the command orchestration in _merge.py.
