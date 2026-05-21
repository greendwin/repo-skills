---
id: s02t1005
slug: base-commit-search-closestmatch-fallback
status: done
---

# Base commit search (closest-match fallback)

**Goal:** When manifest `commit` is `None`, search source repo history for the closest commit. Walk up to ~50 commits touching the skill directory. For each commit, compute file hashes and compare to manifest baseline. Exact hash match → use that commit. No exact match → compute content-weighted distance (sum of added+removed lines via unified diff across all files). Pick the commit with smallest distance.

**Decisions:** Exact match first, line-count unified diff distance, ~50 commit window, files only on one side count as total line count

**Key files:** `src/repo_skills/cli/_merge.py`, `src/repo_skills/git.py`, `src/repo_skills/git_real.py`, `tests/cli/helper.py`, tests

**New GitRepo methods:** `log_commits(path, max_count)`, `get_file_at_commit(commit, path)`
