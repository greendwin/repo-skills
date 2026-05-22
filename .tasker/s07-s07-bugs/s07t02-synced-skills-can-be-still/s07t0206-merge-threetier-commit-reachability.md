---
id: s07t0206
slug: merge-threetier-commit-reachability
status: pending
---

# Merge three-tier commit reachability

## Goal

Before using `entry.commit` as merge base, check reachability. Pinned branch → proceed. Other branch → stop with `--search-base` suggestion. Dangling → auto-search (reusing reporting from slice 2).

## Decisions & Constraints

- **Three-tier check prevents merging unrelated history from other branches.** Creating a merge branch from a commit on another branch would drag in unrelated changes. *Rejected: cherry-pick (adds complexity), auto-proceed (unrelated history).*
- **Commit on pinned branch:** proceed normally (current behavior).
- **Commit exists but not on pinned branch:** stop with error suggesting `--search-base`. User makes conscious choice.
- **Fully dangling commit:** auto-search via `_find_base_commit` (user can't do anything useful with a dangling commit). Print informational message.
- **`--search-base` (from slice 2) bypasses all reachability checks** and forces search regardless.
- Uses `is_ancestor` and `commit_exists_in_any_branch` from slice 3.

## Key files

- `src/repo_skills/cli/_merge.py` — reachability check before using stored commit
- `tests/cli/test_merge.py` — tests for all three tiers

## Acceptance criteria

- Commit on pinned branch: normal merge proceeds
- Commit on another branch: error with `--search-base` suggestion
- Dangling commit: auto-searches with informational output
- `--search-base` bypasses reachability and forces search
