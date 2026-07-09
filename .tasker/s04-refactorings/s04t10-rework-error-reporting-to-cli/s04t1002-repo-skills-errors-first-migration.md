---
id: s04t1002
slug: repo-skills-errors-first-migration
status: done
---

# Repo_skills errors-first migration onto cli-error

## Goal

`repo_skills` routes all error handling through `cli-error` end-to-end: a command that errors renders via a single global `Reporter`, `--version` and no-op paths exit cleanly (status 0), and per-item `update` failures render mid-loop without aborting — with `errors.py` and `fmt_message` deleted and the `cli-error` dependency pinned. Depends on slice 1 (s04t1001).

## Decisions & constraints

- **Single module-global `Reporter(CliReporter)` singleton**, mirroring today's `console` global; no DI. Non-command modules (`git_real`, `config/*`) keep using the global directly. `debug` is a plain mutable attr, so `reporter.debug = debug` is set late in the `_app.py` callback exactly as `console.debug` is today. *Rejected: typer-di injection (non-command modules have no signature); hybrid DI+global (two access paths).*
- **The `Reporter` subclass adds only `running`/`finish`/eoln progress**, overriding `print` to flush pending eoln. One object owns both progress-flush and error-render so a half-written `running()` line is terminated before `print_error`. *Rejected: two objects — reintroduces the split-responsibility drift s11t06 removed.*
- **Typed subclasses subclass `CliError`** (`FileNotInCommitError`, `ConfigBrokenError`, `CommitVerificationError`, `SkillCommitNotFoundError`, `SourceBrokenError`). Each `__init__` stores its attrs and builds the message via `super().__init__(template)` + `prop_*` (`commit`→`prop_id`, `path`→`prop_path`). All `except`-by-type / `.commit`/`.path` access survives. *Rejected: flattening to a discriminator — typed catches are load-bearing control flow.*
- **`NoopError` → `CliExit`** at every raise site, converting to templates with escaped args (e.g. `CliExit("[bold]repo-skills[/bold] [id]{ver}[/id]", ver=ver)`). *Rejected: a `NoopError` shim.*
- **`error_handler` → `reporter.handler()`** at the `main.py` top level. **Non-fatal `_update.py` loop sites (`_pull_sources`, `_run_updates`) → `reporter.report_error(ex)`** (from slice 1), preserving the mid-loop `--debug` traceback. *Rejected: standalone `print_error` (drops traceback); `handler()` in loops (its `SystemExit` aborts the loop).*
- **Debug output conforms to cli-error** (`RUN`/`CWD`/`STDOUT` block form) — stderr-only under `--debug`, not a user contract. *Rejected: overriding `debug_cmd`/`debug_output` to keep old wording.*
- `fmt_ident/data/path/command` are **left in place this slice** (removed in slice 3); only `fmt_message` dies here, coupled to `AppError`.

## Edge cases

- The keyless-prop "hack" in `fmt_message` has no caller — drop it; multi-line raw maps to `CliError.detail()`.
- Reporter must be constructed on `make_console()` so role styles (`id/data/path/cmd/warn/err`) resolve; `derive_stderr_console` handles the stderr console.
- `--version` markup: `ver` from `importlib.metadata.version` is trusted but should still go through the escaped-arg template.
- Cause-chain rendering: cli-error's `print_error` walks `__cause__`/`__context__` (respecting `__suppress_context__`) — matches the existing `render_error` behavior.

## Key files

- `src/repo_skills/errors.py` (deleted), `src/repo_skills/console.py` (Reporter subclass + progress; `fmt_message` removed), `src/repo_skills/main.py`, `src/repo_skills/cli/_app.py` (debug flag, `--version`), `src/repo_skills/cli/_update.py` (loops), `src/repo_skills/git.py` + `src/repo_skills/config/_source.py` (typed subclasses), `src/repo_skills/cli/_merge.py`/`_status.py`/`_update_attach.py`/`config/_utils.py`/`config/_source_registry.py` (typed catches).
- `pyproject.toml` (pin `cli-error>=<slice-1 version>`).
- `tests/test_main.py`, `tests/test_console.py` (debug block-form assertions), plus any test asserting on `NoopError`/`AppError` types.

## Acceptance criteria

- A failing command prints `Error: …` + `caused by:` chain via the global `Reporter` and exits 1; `--version` and no-op paths exit 0 with their message.
- `except FileNotInCommitError`/`ConfigBrokenError`/`CommitVerificationError`/`SkillCommitNotFoundError`/`SourceBrokenError` still catch, and `.commit`/`.path` still read.
- A per-item `update` failure renders (with traceback under `--debug`) and the loop continues to the next item.
- `errors.py` and `fmt_message` no longer exist; `grep NoopError|AppError|error_handler|render_error src/` is empty.
- `uv run tox` green (all environments).
