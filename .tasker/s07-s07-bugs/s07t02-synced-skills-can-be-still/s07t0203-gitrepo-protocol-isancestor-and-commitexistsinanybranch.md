---
id: s07t0203
slug: gitrepo-protocol-isancestor-and-commitexistsinanybranch
status: done
---

# GitRepo protocol: is_ancestor and commit_exists_in_any_branch

## Goal

Add two new methods to the GitRepo protocol, implement in RealGitRepo, and add to FakeGitRepo test helper.

## Decisions & Constraints

- **Two separate methods because merge needs both.** `is_ancestor` checks if commit is on the pinned branch. `commit_exists_in_any_branch` distinguishes "on another branch" from "fully dangling." *Rejected: single method (merge needs the distinction for three-tier behavior).*
- **`is_ancestor(commit, branch) -> bool`** — maps to `git merge-base --is-ancestor <commit> <branch>`.
- **`commit_exists_in_any_branch(commit) -> bool`** — maps to `git branch --contains <commit>`.
- **FakeGitRepo must support controllable state** for both methods so tests can simulate all three tiers.

## Key files

- `src/repo_skills/git.py` — protocol additions
- `src/repo_skills/git_real.py` — real implementations
- `tests/cli/helper.py` — FakeGitRepo additions

## Acceptance criteria

- `is_ancestor(commit, branch)` returns True when commit is reachable from branch tip, False otherwise
- `commit_exists_in_any_branch(commit)` returns True when commit is on any branch, False when dangling
- FakeGitRepo supports both methods with controllable state
