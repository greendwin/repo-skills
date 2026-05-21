---
id: s06t03
slug: pretty-error-reporting-with-debug
status: done
---

# Pretty error reporting with `--debug` support

## Decisions

- **Global `--debug` flag via `app.callback()`** — cross-cutting concern, shouldn't pollute individual command signatures
- **Single `AppError` class in `_errors.py`** — one class separates "known error" from "unhandled crash"; no hierarchy needed since there's no branching behavior on error type
- **Exception handler as `main()` wrapper around `app()`** — avoids fighting Typer's own exception hooks, gives full control over formatting
- **Module-level debug flag in `_app.py`** — `set_debug()`/`get_debug()` pair; simple for single-threaded CLI, accessible from outside Typer's call stack
- **Unhandled exception chain: outermost first, then indented `caused by:` lines** — most actionable message on top, root cause below
- **Disable Typer's pretty exceptions entirely** (`pretty_exceptions_enable=False`) — single source of truth for error formatting, no competing formatters
- **`Console()` on stdout with auto-detection** — Rich handles `NO_COLOR` automatically; all error output goes to stdout (not stderr), simplifying tests
- **Migration: `typer.echo(msg, err=True)` + `raise typer.Exit(1)` → `raise AppError(msg)`** — rich markup supported in error messages

## Subtasks

- [x] [s06t0301](s06t0301-apperror-main-wrapper.md): `AppError` + `main()` wrapper
- [x] [s06t0302](s06t0302-migrate-all-error-sites-to.md): Migrate all error sites to `AppError`
