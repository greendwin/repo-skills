---
id: s02t10
slug: skills-merge-continue-abort
status: pending
---

# `skills merge` + `--continue` / `--abort`

**Goal:** Full merge flow adapted for multi-provider. Auto-detect source/provider. Git branch from stored commit, rebase, FF-only. Conflict resolution with `--continue`/`--abort`.
**Decisions:** Git branching merge, auto-detect `--from`/`--to`, merge only touches source.
**Key files:** `src/repo_skills/main.py`, `src/repo_skills/_git.py`, `src/repo_skills/_git_real.py`, tests
