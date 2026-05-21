---
id: s02t1002
slug: skills-merge-continue
status: done
---

# `skills merge --continue`

**Goal:** Finalize a merge. Detect state: if rebase in progress run `git rebase --continue` (support user having done it manually). FF pinned branch to merge branch tip. Copy merged files back to source provider's install path. Update manifest for that provider only (new commit + fresh hashes). Delete merge branch, checkout pinned branch. Detect empty merge ("nothing to merge, already up to date"). Three-tier branch identification: (1) current branch, (2) single merge branch auto-detect, (3) require args.

**Decisions:** Handles rebase internally, strict dirty-tree check, copy-back to source provider only, manifest update for that provider, empty merge detection, FF failure → error with instructions (no auto-pull)

**Key files:** `src/repo_skills/cli/_merge.py`, `src/repo_skills/git.py`, `src/repo_skills/git_real.py`, `tests/cli/helper.py`, tests

**New GitRepo methods:** `is_rebasing()`, `rebase_continue()`, `fast_forward(branch)`, `delete_branch(name)`, `list_branches(pattern)`
