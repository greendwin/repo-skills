---
id: s05t01
slug: apperror-main-wrapper
status: done
---

# `AppError` + `main()` wrapper

## Goal
One `raise AppError("message")` flows through the wrapper and prints `Error: message` on stdout. `--debug` shows traceback. Unhandled exceptions print chain with `caused by:` lines. Entry point changes from `main:app` to `main:main`.

## Decisions
- `AppError` in `src/repo_skills/_errors.py` with `message` field supporting rich markup
- Global `--debug` callback on root `app` in `_app.py`
- Module-level `set_debug()`/`get_debug()` in `_app.py`
- `pretty_exceptions_enable=False` on app
- `main()` wrapper in `main.py`: catch `AppError` → `[red]Error:[/red] message`; catch `Exception` → outermost first + indented `caused by:` chain; `--debug` → show traceback
- `Console()` on stdout with auto-detection
- Entry point `main:app` → `main:main` in `pyproject.toml`
- Update `assert_invoke` in test helper for new error handling

## Key files
- `src/repo_skills/_errors.py` (new)
- `src/repo_skills/cli/_app.py`
- `src/repo_skills/main.py`
- `pyproject.toml`
- `tests/cli/helper.py`
- tests for: AppError, unhandled exception chain, --debug traceback
