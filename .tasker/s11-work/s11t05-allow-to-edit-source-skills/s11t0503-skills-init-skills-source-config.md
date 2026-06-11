---
id: s11t0503
slug: skills-init-skills-source-config
status: in-review
---

# `skills init` + `skills source config` command surface

## Goal

Expose the shared init/config implementation under two visible, intent-named commands — `skills init` ("first-time setup") and `skills source config` ("edit settings") — both accepting `--name`/`--branch`/`--skills-dir` and both create-or-edit. Keep `skills source init` as a hidden back-compat alias; remove the old erroring `init`-redirect. Update `CONTEXT.md`'s Source definition.

## Decisions & constraints

- **ADR 0003** — two intent-named commands over one idempotent impl; they must never drift (both delegate to the shared function from the first slice). *Rejected: one overloaded `source init`; dropping `source init` entirely.*
- **Supersedes s06t10** — the old hidden `init` redirect (errored with "Did you mean `skills source init`?") is removed; `skills init` now performs setup.
- `skills source init` remains as a **hidden** alias of `skills source config` for muscle memory and existing tests.
- Update the `CONTEXT.md` "Source" row to cite `skills init` (configurable later via `skills source config`) instead of `skills source init`.

## Edge cases

- `skills init` on a fresh repo → creates the source.
- `skills source config` on an existing source → edits it.
- Hidden `skills source init` still works (delegates to the same impl).

## Key files

- `src/repo_skills/cli/_source.py`
- `src/repo_skills/cli/_app.py` (command registration; remove `init_redirect`)
- `tests/cli/test_source_init.py`
- `CONTEXT.md`

## Acceptance criteria

- `skills init` and `skills source config` both create-or-edit identically, with all three options.
- Hidden `skills source init` alias still works; the old erroring redirect is gone.
- `CONTEXT.md`'s Source definition cites the new command names.
