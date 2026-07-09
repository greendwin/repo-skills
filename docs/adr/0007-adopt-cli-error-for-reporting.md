# Adopt cli-error for CLI error reporting and styling

## Context

`repo_skills` grew its own error/reporting stack: `AppError` (+ typed
subclasses), `NoopError`, `render_error`/`error_handler` in `errors.py`, and a
`fmt_ident/data/path/command`/`fmt_message` styling vocabulary plus a `Console`
in `console.py`. The same shapes — a Rich-markup error carrying hint/props, a
clean-exit signal, a debug-gated reporter, a role-based style theme — now exist
as a reusable, separately-versioned package, `cli-error` (authored in-house).
Maintaining a parallel copy means every styling/error decision (e.g. the
s11t06 render-primitive unification) has to be re-made and kept from drifting.

## Decision

Depend on `cli-error` and route error reporting and CLI styling through it:

- `AppError` → `CliError` (typed subclasses stay, subclassing `CliError`);
  `NoopError` → `CliExit`; `error_handler` → `CliReporter.handler()`.
- A module-global `Reporter(CliReporter)` singleton mirrors the previous
  `console` global (single access path; non-command modules keep using it).
  The subclass adds only the app-specific `running`/`finish`/eoln progress API,
  which stays out of the general lib.
- Non-fatal, mid-loop failures use `CliReporter.report_error()` (render without
  exit); `handler()` delegates its rendering to the same method, so `SystemExit`
  is the only thing the fatal path adds — preserving the single render primitive.
- The `fmt_*` vocabulary is deleted; call sites move to `reporter.print`
  templates with escaped args (`[id]`/`[data]`/`[path]`/`[cmd]` roles). The
  `status` color-as-data markup (`[green]synced`, `[dim magenta]orphan`, …)
  stays raw — it is not a semantic role (ADR-0001 exception).

ADR-0001 remains the human-readable styling **contract**; cli-error's
`DEFAULT_STYLES` (`id/data/path/cmd/warn/err`) is now its **implementation**.

## Considered Options

- **Keep the in-house `errors.py`/`fmt_*` stack.** Rejected: it is a parallel
  copy of a maintained package; each fix (colon/cause-chain drift, render
  unification) must be re-made here and guarded against re-drift.
- **Extract an internal, unpublished module** instead of depending on the
  package. Rejected: the package already exists and is reused beyond this repo;
  a private fork forgoes that shared maintenance.

## Consequences

- `cli-error` currently requires Python ≥3.12 while `repo_skills` stays
  `>=3.10`; a 3.10-compatible `cli-error` release lands first (the initial
  slice) so every `repo_skills` commit resolves and `tox` stays green.
- Debug diagnostics adopt cli-error's wording/format (`RUN`/`CWD`/`STDOUT`
  block form), replacing the previous `COMMAND:`/per-line `stdout:` output.
