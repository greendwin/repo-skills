---
id: s10t021003
slug: skills-merge-abort
status: done
---

# `skills merge --abort`

**Goal:** Abort a merge. Resilient to any state: abort rebase if in progress (handles user having already run `git rebase --abort` manually). Delete merge branch, checkout pinned branch. No dirty-tree check — abort should always work.

**Decisions:** Always cleans up, no dirty-tree check, resilient to manual abort

**Key files:** `src/repo_skills/cli/_merge.py`, `src/repo_skills/git.py`, `src/repo_skills/git_real.py`, `tests/cli/helper.py`, tests

**New GitRepo methods:** `rebase_abort()`
