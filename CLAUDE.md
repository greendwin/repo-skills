## Domain

See `CONTEXT.md` for project terminology (source, skill, provider, etc.).

## Development

* On any development iteration, the final step is to run `uv run tox` (all environments).
* Always fix **all** reported `tox` issues including **pre-existing**.
* Write comments maximally compact and concise — why use many token when few token do trick. Drop filler, prefer fragments over full sentences, cut anything the code already says; keep only the non-obvious *why*. Code, commands, error strings, paths stay exact.
* Never include tasks IDs into code comments (e.g. `s12t03`, `s01` in section headers or inline comments).
* Never drop a `TODO` unless you can guarantee it is already resolved. This applies to any change — resolving merge conflicts (preserve `TODO`s from either side), implementing features, or fixing bugs: a `TODO` still actual and not addressed by your change must be preserved. Exception: a `TODO` may be deleted when its removal is explicitly approved during a triage review (e.g. `/todo-triage`) after the question it raised has been resolved.
* When finishing a task change its status to `in-review` by MCP tool `review_task`.

## Python Guide

* Never use `type: ignore` if it can be fixed normally.
* Never use `unittest.mock.patch`, use `monkeypatch`.
* Never use inline imports inside methods and tests.
* Always use `assert_invoke` helper instead of `CliRunner`.

## Conventions

Task-coupled skills read `docs/agents/task-tracker.md` to resolve task-tracker verbs and statuses.

`dev-loop` reads `docs/agents/dev-loop.md` to resolve the reviewer rosters.