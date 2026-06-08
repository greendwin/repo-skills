---
id: s10t021001
slug: skills-merge-name-basic-start
status: done
---

# `skills merge <name>` — basic start flow

**Goal:** Happy path merge start. Manifest has `commit != None`, auto-detect single diverged provider, validate clean tree, pull, create merge branch `skill-merge/<provider>/<name>`, copy provider files, auto-commit (`chore: merge <skill> from <provider>`), start rebase. Always stops and tells user to run `--continue` (no auto-finalize yet). Error if `commit` is `None`.

**Decisions:** Auto-detect `--from` (error when ambiguous), auto-checkout pinned branch, pull + `--offline`, branch naming `skill-merge/<provider>/<name>`, auto-commit message, require `commit != None`

**Key files:** `src/repo_skills/cli/_merge.py` (new), `src/repo_skills/git.py`, `src/repo_skills/git_real.py`, `tests/cli/helper.py`, tests

**New GitRepo methods:** `create_branch(name, from_commit)`, `checkout(branch)`, `rebase(onto)`, `commit_all(message)`
