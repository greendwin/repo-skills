---
id: s01t0301
slug: wrapper-script-and-env-scaffolding
status: pending
---

# Wrapper script and env scaffolding

## Goal

`./integration/run.sh` with subcommands `setup`, `test`, `teardown`, `shell` that provides isolated environment for integration tests.

## Decisions & constraints

- Wrapper does minimal env isolation only — sets `HOME` and `XDG_CONFIG_HOME` to temp dirs. Git repo construction stays in pytest fixtures.
- Subcommand interface: single script, each phase is a named action.
- Must work for both human (`shell` for manual poking) and agent (`setup` → `test` → `teardown`).
- The env path must be printed by `setup` so callers can reuse it.
- Not in tox — run explicitly via wrapper script.

## Edge cases

- Running `teardown` when no env exists (should be a no-op or gentle warning)
- Running `test` without prior `setup` (should auto-setup, run, then teardown)

## Key files

- `integration/run.sh` (new)

## Acceptance criteria

- `./integration/run.sh setup` creates a temp dir with `logs/` subdirectory and prints its path
- `./integration/run.sh shell` opens a bash session with `HOME`/`XDG_CONFIG_HOME` pointing into the env
- `./integration/run.sh teardown <path>` removes the env
- `./integration/run.sh test` runs pytest inside the isolated env (auto-setup/teardown)
- Script is executable and has usage help
