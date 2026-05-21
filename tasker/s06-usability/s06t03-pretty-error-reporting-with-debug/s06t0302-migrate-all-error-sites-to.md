---
id: s06t0302
slug: migrate-all-error-sites-to
status: done
---

# Migrate all error sites to `AppError`

## Goal
Replace every `typer.echo(msg, err=True)` + `raise typer.Exit(1)` with `raise AppError(msg)`. All existing tests pass with updated assertions.

## Decisions
- Migration: `typer.echo(msg, err=True)` + `raise typer.Exit(1)` → `raise AppError(msg)`
- Rich markup supported in error messages

## Key files
- `src/repo_skills/cli/_deps.py` (2 sites)
- `src/repo_skills/cli/_install.py` (5 sites)
- `src/repo_skills/cli/_update.py` (2 sites)
- `src/repo_skills/cli/_source.py` (2 sites)
- `tests/cli/test_install.py`, `test_update.py`, `test_source_init.py`, `test_uninstall.py` (update assertions)
