---
id: s04t10
slug: rework-error-reporting-to-cli
status: pending
---

# Rework error reporting to 'cli-error' lib

## Context

`repo_skills` maintains its own error/reporting stack — `AppError` (+ typed subclasses), `NoopError`, `render_error`/`error_handler` in `errors.py`, and a `fmt_ident/data/path/command`/`fmt_message` styling vocabulary plus a `Console` in `console.py`. The same shapes now exist as a reusable, separately-versioned in-house package, `cli-error` (`CliError`, `CliExit`, `CliReporter`, a role-based theme). Rework `repo_skills` to depend on `cli-error` so styling/error decisions (e.g. the s11t06 render-primitive unification) live in one maintained place instead of a drifting parallel copy. Recorded as ADR-0007.

## Decisions

- **Adopt the published `cli-error` package** (not an internal unpublished module). *Rejected: keeping the in-house `errors.py`/`fmt_*` stack — a parallel copy of a maintained package where each fix must be re-made and guarded from re-drift. Rejected: a private/vendored fork — forgoes the shared maintenance of a package already reused beyond this repo.*
- **Python floor stays `>=3.10`** — `cli-error` must meet `repo_skills`, not vice-versa. `cli-error` 0.1.2 requires `>=3.12`, so a 3.10-compatible `cli-error` release lands *first* (slice 1) before the migration, keeping every commit resolvable and `tox` green. *Rejected: bumping `repo_skills` to `>=3.12` — the floor is deliberately kept low.*
- **Full absorption is the end-state, delivered in reviewable slices** (errors-first, then fmt-absorption) — the point is to stop maintaining a parallel styling/error vocabulary, but each slice stays green and reviewable.
- **Single module-global `Reporter(CliReporter)` singleton**, mirroring today's `console` global; no DI. *Rejected: typer-di injection — non-command modules (`git_real`, `config/*`) have no signature to inject into and would need reporter params threaded through unrelated call chains. Rejected: hybrid DI+global — two access paths are worse than one.* The `debug` flag is a plain mutable attr, so the "construct global, set `reporter.debug` late in the `_app.py` callback" pattern transfers verbatim.
- **The `Reporter` subclass adds only `running`/`finish`/eoln progress** — its sole app-specific addition. One object owns both progress eoln-flush and error render, because when an exception escapes a `running()` block the half-written line must be flushed before `print_error`; coupling them keeps that coordination in one place. *Rejected: two objects (separate progress `Console` + reporter) — reintroduces the split-responsibility drift s11t06 removed.*
- **Typed error subclasses stay, subclassing `CliError`** — `FileNotInCommitError`, `ConfigBrokenError`, `CommitVerificationError`, `SkillCommitNotFoundError`, `SourceBrokenError`. `CliError` is a plain `Exception`, so subclasses keep their data attrs and `except`-by-type control flow; only visible change is props gaining semantic color roles. *Rejected: flattening to plain `CliError` with a discriminator — the typed catches are load-bearing control flow, not just formatting.*
- **`NoopError` → `CliExit`** at every raise site, converting messages to templates with escaped args (`--version` etc.). *Rejected: a `NoopError` shim over `CliExit` — preserves the vocabulary the task exists to retire.*
- **`report_error(ex)` (non-fatal render, no exit) added upstream to `cli-error`'s `CliReporter`**, and `handler()` refactored to delegate to it. Non-fatal mid-loop failures (`_update.py` `_pull_sources`/`_run_updates`) call `reporter.report_error`; the fatal top level keeps `handler()`. Preserves s11t06's single non-fatal render primitive (debug traceback survives under `--debug`). *Rejected: calling standalone `print_error` in loops — drops the mid-loop debug traceback. Rejected: routing loops through `handler()` — its `SystemExit` aborts the loop.*
- **`SystemExit` stays in `handler()`** as the sole thing it adds over rendering — it is the error→exit-code boundary and is orthogonal to the non-fatal loop case (a context-manager handler is inherently fatal-shaped). *Rejected: decoupling exit from render via a swallowing handler + `reporter.exit_code` — a context manager that suppresses every exception is surprising and adds a mandatory second line at every entry point.*
- **Delete `fmt_ident/data/path/command`; call sites move to `reporter.print` templates with escaped args** (`[id]`/`[data]`/`[path]`/`[cmd]` roles), upgrading manual `escape()` to auto-escaping. The `status` color-as-data markup (`[green]synced`, `[dim magenta]orphan`, …) stays raw — it is not a semantic role (ADR-0001 exception). *Rejected: thin `fmt_*` wrappers emitting role markup — retains the vocabulary the task retires.*
- **Debug output conforms to `cli-error`'s wording/format** (`RUN`/`CWD`/`STDOUT` block form), replacing `COMMAND:`/per-line `stdout:`. *Rejected: overriding `debug_cmd`/`debug_output` in the subclass — re-implements the exact helpers `cli-error` is adopted to stop maintaining.* Diagnostics are stderr-only under `--debug`, not a user-facing contract.

## Open questions

- None outstanding.

## Out of scope

- Promoting `running`/`finish`/eoln progress into `cli-error` — stays in the `repo_skills` `Reporter` subclass; promote later in its own `cli-error` release only if it proves generic.
- `CONTEXT.md` changes — `cli-error`/`reporter` are implementation vocabulary, not domain terms; the domain glossary stays untouched.
- The `cli-error`-side work itself is specced in `CLI-ERROR-FEATURE-REQUEST.md` at the repo root and tracked here as slice 1.

## Subtasks

- [ ] [s04t1001](s04t1001-cli-error-release-3-10.md): Cli-error release: 3.10 support + report_error + handler delegation
- [ ] [s04t1002](s04t1002-repo-skills-errors-first-migration.md): Repo_skills errors-first migration onto cli-error
- [ ] [s04t1003](s04t1003-repo-skills-fmt-absorption-retire.md): Repo_skills fmt-absorption: retire fmt_* for cli-error roles
