---
id: s10t0210
slug: skills-merge-continue-abort
status: done
---

# `skills merge` + `--continue` / `--abort`

**Goal:** Full merge flow adapted for multi-provider. Auto-detect source/provider. Git branch from stored commit, rebase, FF-only. Conflict resolution with `--continue`/`--abort`.
**Key files:** `src/repo_skills/main.py`, `src/repo_skills/_git.py`, `src/repo_skills/_git_real.py`, tests

## Decisions

- **Direction is provider→source only.** `merge` brings provider edits back to the source repo. Source→provider is `update`.
- **Auto-detect `--from` provider.** When exactly one provider has a diverged copy, auto-detect. When multiple providers diverged, error and require `--from <provider>`.
- **Base commit from manifest or history search.** Use manifest `commit` field when present. When `None` (e.g. `install --force`), search source history: exact file-hash match first, then closest commit by line-count unified diff distance (sum of added+removed lines across all files), bounded to ~50 commits.
- **Branch naming: `skill-merge/<provider>/<name>`.** Supports parallel merges from different providers for the same skill.
- **Branch identification for `--continue`/`--abort`:** (1) current branch if it's a merge branch, (2) auto-detect if exactly one merge branch exists, (3) require name / `--from` to disambiguate.
- **Auto-checkout pinned branch.** On merge start, auto-checkout the source repo's pinned branch (no dirty-tree issue since clean check passes first). Deprecate/remove `--any-branch`; user changes the pinned branch instead.
- **Pull by default, `--offline` to skip.** Consistent with `install`/`update`.
- **Auto-commit on merge branch.** Message: `chore: merge <skill> from <provider>`. User never provides this message.
- **Start rebase automatically.** After auto-commit, rebase onto pinned branch starts immediately.
- **Clean rebase → auto-finalize.** If rebase has no conflicts: FF pinned branch, copy merged files back to source provider, update manifest, delete merge branch. Print "merge complete."
- **Conflicts → stop and require `--continue`.** Print conflict info and instructions.
- **`--continue` handles rebase internally.** Runs `git rebase --continue` if rebase is in progress; also supports user having run it manually (rebase already done). Then: FF pinned branch, copy-back, manifest update, cleanup.
- **`--abort` is always resilient.** Aborts rebase if in progress (handles user having already aborted manually). Deletes merge branch, checks out pinned branch. No dirty-tree check.
- **Dirty-tree check:** strict on `merge` start and `--continue`; skip on `--abort`.
- **Post-merge copy-back.** Merged files are copied back to the source provider's install path. Manifest updated for that provider only (new commit + fresh hashes). Other providers are not touched — they sync via `update`.
- **Empty merge detection.** If after rebase the merge branch has no commits ahead of pinned branch, print "nothing to merge, already up to date" and clean up.
- **FF failure → error with instructions.** If pinned branch moved forward during merge, tell user to pull and retry `--continue`. No auto-pull mid-merge.
- **No restrictions on merge branch.** User can add extra commits, amend, rebase manually, etc. `--continue` just does FF from wherever the branch is.
- **Git implementation: extend existing pattern.** Add branch/rebase/FF methods to `GitRepo` protocol + `FakeGitRepo`. Tests verify merge logic in pyfakefs, not git mechanics.

## Separate task: pinned branch

`source init` should capture the current branch as the "pinned branch." Merge and other commands target this branch instead of assuming `main`. User can change the pin explicitly. This replaces `--any-branch`.

## Subtasks

- [x] [s10t021001](s10t021001-skills-merge-name-basic-start.md): `skills merge <name>` — basic start flow
- [x] [s10t021002](s10t021002-skills-merge-continue.md): `skills merge --continue`
- [x] [s10t021003](s10t021003-skills-merge-abort.md): `skills merge --abort`
- [x] [s10t021004](s10t021004-autofinalize-on-clean-rebase.md): Auto-finalize on clean rebase
- [x] [s10t021005](s10t021005-base-commit-search-closestmatch-fallback.md): Base commit search (closest-match fallback)
