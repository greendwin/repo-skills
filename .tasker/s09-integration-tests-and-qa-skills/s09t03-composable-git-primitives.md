---
id: s09t03
slug: composable-git-primitives
status: pending
---

# Composable git primitives

## Goal

Helper functions to build real git repo states for integration tests.

## Decisions & constraints

- Composable primitives as foundation — each does one git or filesystem operation.
- Return/mutate `IntegrationEnv`.
- Must use `git` subprocess calls (not `RealGitRepo`) to avoid testing the tool with itself.
- All operations use the isolated env, not real user directories.

## Key files

- `integration/git_helpers.py` (new)

## Acceptance criteria

- `create_source_repo(env)` creates a git repo with initial commit, stores path in env
- `add_skill(env, "tdd", content="# tdd")` creates a skill dir with `SKILL.md` and commits
- `create_provider_dir(env, "claude")` creates a provider install directory
- `make_commit(repo, msg)` stages all and commits
- `create_clone(origin, dest)` clones a repo
- Primitives compose cleanly (e.g. `create_source_repo` then `add_skill` then `add_skill` produces a repo with two skills and correct git history)
