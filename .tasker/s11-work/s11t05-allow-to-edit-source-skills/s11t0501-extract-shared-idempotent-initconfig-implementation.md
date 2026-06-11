---
id: s11t0501
slug: extract-shared-idempotent-initconfig-implementation
status: done
---

# Extract shared idempotent init/config implementation

## Goal

Extract the create-or-update logic behind `source init` into one shared function so the current `source init` (fresh init + reinit) routes through it. Existing source-init tests pass unchanged. This is the single implementation the two future commands (`skills init`, `skills source config`) will share so they can't drift.

## Decisions & constraints

- **Single shared impl** — `skills init` and `skills source config` (next slices) must both delegate here; no duplicated init logic.
- Pure refactor — no new options or behavior in this slice.
- Preserve the existing grouped reinit feedback (`key: old → new` detail lines under an `Updated source X.` / `Registered source X.` / `Source X already initialized.` header).

## Key files

- `src/repo_skills/cli/_source.py` (`source_init`, `_handle_reinit`)
- `tests/cli/test_source_init.py`

## Acceptance criteria

- All existing `source init` and reinit tests pass against the extracted shared function.
- Fresh init, rename, branch change, and true no-op feedback paths are unchanged.
