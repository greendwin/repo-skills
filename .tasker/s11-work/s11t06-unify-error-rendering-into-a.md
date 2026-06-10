---
id: s11t06
slug: unify-error-rendering-into-a
status: done
---

# Unify error rendering into a single primitive

There are three sites that encode the same error-rendering decision (debug -> traceback; AppError -> print markup-aware `ex.message`; else -> `escape(str(ex))`):

- `error_handler` in `src/repo_skills/errors.py`
- the `_print_error` helper used by `_pull_sources` and `_run_updates` in `src/repo_skills/cli/_update.py`

The copies have drifted:
- Colon placement differs: `error_handler` prints `[red]Error:[/red]` (colon inside the tag) while `_print_error` prints `[red]Error[/red]:` (colon outside).
- `error_handler` walks the `__cause__`/`__context__` chain and prints `caused by:` lines; `_print_error` does not, so a non-fatal per-source/per-skill failure with a wrapped cause silently drops that detail.

Promote a single rendering primitive (e.g. `console.print_error(ex)` or a free function in `errors.py`) that owns the debug / AppError / escape / cause-chain logic, and have both `error_handler` and the two `update` loops call it. Collapses three copies into one, removes the colon/cause-chain drift, and makes "how do we render a fatal vs non-fatal error" a single decision.

App-wide blast radius (every command's error output), so split out of the pull-resilience task. Surfaced by the dev-loop refactor review for the pull-failure-resilience change.
