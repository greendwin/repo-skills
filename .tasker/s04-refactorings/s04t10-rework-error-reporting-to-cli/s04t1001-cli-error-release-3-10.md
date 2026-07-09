---
id: s04t1001
slug: cli-error-release-3-10
status: pending
---

# Cli-error release: 3.10 support + report_error + handler delegation

## Goal

A published `cli-error` version (successor to 0.1.2) that: (1) resolves on Python ≥3.10, (2) exposes `CliReporter.report_error(ex)` — non-fatal render (debug traceback + message + cause chain), no `SystemExit`, and (3) has `handler()` delegate its error rendering to `report_error`. Unblocks the `repo_skills` migration (slices 2–3). **Work happens in the `cli-error` repo**; this subtask tracks the dependency landing and the resulting version to pin.

## Decisions & constraints

- **Floor `>=3.10`.** `repo_skills` stays on `>=3.10` and must not be dragged up, so `cli-error` (currently `requires-python = ">=3.12"`) must backport. Landing this first keeps every `repo_skills` commit resolvable and `tox` green. *Rejected: bumping `repo_skills` to `>=3.12`.*
- **`report_error` upstreamed, not a `repo_skills` subclass method** — non-fatal reporting is the mirror of `handler()` and is the reporter's own job; every CLI with a per-item loop needs it. Body:
  ```python
  def report_error(self, ex: Exception) -> None:
      self.debug_traceback()
      print_error(ex, self.console)
  ```
- **`handler()` delegates to `report_error`**, keeping `SystemExit` as the *only* thing it adds over rendering (the error→exit-code boundary). `SystemExit` is orthogonal to the non-fatal loop case — a context-manager handler is inherently fatal-shaped. *Rejected: a swallowing handler + `reporter.exit_code`.*
- Progress `running`/`finish`/eoln is **out of scope** for cli-error — it stays in the `repo_skills` `Reporter` subclass (slice 2).

## Edge cases

- 3.12-only footguns when backporting: `typing.Self` (3.11) in `_errors.py` → `typing_extensions.Self` or a `TypeVar`-bound return; runtime-position `X | Y` unions; new stdlib signatures.
- `report_error` must be a no-op-safe traceback outside an `except` block (cli-error's `debug_traceback` already guards on `sys.exc_info()`).
- Widen cli-error's CI matrix to include 3.10/3.11 so the floor stays honest.

## Key files

- External: `greendwin/cli-error` repo — `src/cli_error/_reporter.py` (`report_error`, `handler`), `src/cli_error/_errors.py` (`Self` usage), `pyproject.toml` (`requires-python`), CI matrix.
- This repo: `CLI-ERROR-FEATURE-REQUEST.md` (the spec to hand off).

## Acceptance criteria

- `pip install cli-error==<new>` resolves on Python 3.10 and 3.11.
- `CliReporter.report_error(ex)` renders the same output as `handler()`'s error branch but does not raise `SystemExit`.
- `handler()` still exits 0 on `CliExit` and 1 on other exceptions, with rendering routed through `report_error`.
- The new version is published; the version string is recorded for the slice-2 dependency pin.
