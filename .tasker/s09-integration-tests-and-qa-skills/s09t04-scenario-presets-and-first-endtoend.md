---
id: s09t04
slug: scenario-presets-and-first-endtoend
status: pending
---

# Scenario presets and first end-to-end test

## Goal

Preset functions for common scenarios + a first passing integration test that exercises the full `source init` → `install` → `status` → `uninstall` lifecycle.

## Decisions & constraints

- Presets are thin wrappers over primitives from slice 3.
- First test proves the entire integration stack works end-to-end (tracer bullet).
- Test must run via `./integration/run.sh test` and produce inspectable logs.

## Key files

- `integration/presets.py` (new)
- `integration/tests/test_lifecycle.py` (new)

## Acceptance criteria

- `setup_basic_source(env)` creates a source repo with 2-3 skills
- `setup_installed_env(env)` creates source + provider + installed skills
- Lifecycle test passes: `source init` → `install tdd` → `status` shows "synced" → `uninstall tdd` → `status` shows "available"
- Log files in `$ENV/logs/` contain all command outputs
- Test is discoverable by pytest via the wrapper script
