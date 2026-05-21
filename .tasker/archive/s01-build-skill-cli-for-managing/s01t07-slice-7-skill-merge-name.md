---
id: s01t07
slug: slice-7-skill-merge-name
status: cancelled
---

# Slice 7 — `skill merge <name>` + `--continue` / `--abort`

**Goal:** Full merge flow — create `skill-merge/<name>` branch from stored commit, commit local edits, rebase onto current branch, fast-forward main on success (fail if can't FF, never push). `--continue` copies resolved files, updates manifest, FF main, deletes branch. `--abort` runs `git rebase --abort`, deletes branch. Stateless — branch existence is state. Dirty working tree aborts early. Parallel merges supported; `<name>` required if multiple `skill-merge/*` branches exist.
**Decisions:** Merge flow, stateless, FF-only, never push, dirty tree check.
**Key files:** `src/skill_cli/_main.py`, `src/skill_cli/_git.py`, tests
