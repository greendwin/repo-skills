---
id: s16t34
slug: refactor-branch-naming-parsing-cluster
status: pending
---

# Refactor: Branch-naming/parsing cluster is a cohesive seam ripe for extraction; _merge.py sits at 1330 lines (>1k)

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Branch-naming/parsing cluster is a cohesive seam ripe for extraction; _merge.py sits at 1330 lines (>1k)"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py — branch helpers (_merge_branch_name/_merge_branch_prefix/_list_merge_branches/_current_or_listed_merge_branches/_detect_merge_branch/_split_merge_branch/_active_merge_branch_for/_parse_merge_branch) scattered across module; file totals 1330 lines
- severity: minor

This change introduces a self-contained branch-name encoding vocabulary (prefixes, name builder, prefix detector, lister, current-or-listed precedence, non-raising splitter, raising parser, active-for lookup). They form one cohesive concept — merge-branch identity — but live interleaved with command orchestration in an already >1k-line module. Per the lens's file-size rule and the diff being the natural moment the cluster crystallized, extracting it into a focused `_merge_branches.py` would shrink _merge.py back below the threshold, give the encoding scheme one home (where the module-top intent note also belongs), and let command code import a small typed surface instead of co-housing eight private string helpers. The change trends the right way (it deletes _merge_state.py), so this is a follow-up decomposition, not a regression introduced here. (Tracker side-task s16t15.)

## Suggested fix

Move the branch-name cluster (the eight helpers above plus MERGE_BRANCH_STEM/MERGE_BRANCH_PREFIX/MERGE_KEEP_BRANCH_PREFIX/_MERGE_PREFIXES and the module-top intent comment) into a new `src/repo_skills/cli/_merge_branches.py`, exposing the small set _merge.py actually calls. Optionally also lift _score_commit/_compute_distance into a `_merge_base.py`, leaving _merge.py as command orchestration. Keep behavior identical; this is pure relocation.
