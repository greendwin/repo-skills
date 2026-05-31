---
id: s09t02
slug: integrationenv-dataclass-cli-runner-helper
status: pending
---

# IntegrationEnv dataclass, CLI runner helper, and log capture

## Goal

Python test infrastructure: `IntegrationEnv` dataclass, `run_skills()` subprocess helper that returns a typed result and writes log files to `$ENV/logs/`.

## Decisions & constraints

- Subprocess invocation via `run_skills()` — all CLI calls go through `subprocess.run`.
- Result dataclass with `stdout`, `stderr`, `exit_code`, `command`, `duration`.
- Log files always written to `$ENV/logs/` with sequential numbering (e.g. `001-install.stdout`, `001-install.stderr`).
- Must work with env vars set by the wrapper script (`HOME`, `XDG_CONFIG_HOME`).
- Logs must persist after test run for human/agent inspection.

## Key files

- `integration/helpers.py` (new)
- `integration/conftest.py` (new)

## Acceptance criteria

- `IntegrationEnv` holds `home`, `config_dir`, `logs_dir` and paths are derived from env vars or created under a temp dir
- `run_skills("status")` returns a result with stdout, stderr, exit_code, command, duration
- Each invocation creates a numbered log file pair in `$ENV/logs/`
- A failing command returns exit_code != 0 without raising
- pytest fixture yields an `IntegrationEnv` instance
