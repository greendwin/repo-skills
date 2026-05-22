---
id: s06t1002
slug: hidden-skills-init-redirect-command
status: done
---

# Hidden `skills init` redirect command

## Goal

Top-level `skills init` command (hidden from help) prints a helpful redirect message and exits non-zero.

## Decisions

- Hidden from `--help` output
- Message: "Did you mean 'skills source init'? Use 'skills source init' to register a skill source."
- Non-zero exit code (use `AppError`)

## Key files

- `src/repo_skills/cli/_source.py` — register hidden command on `app`
- `tests/cli/test_source_init.py` — new test class for the redirect
