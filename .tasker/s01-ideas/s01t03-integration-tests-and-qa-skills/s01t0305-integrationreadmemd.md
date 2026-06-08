---
id: s01t0305
slug: integrationreadmemd
status: pending
---

# Integration/README.md

## Goal

Document the integration test framework so that humans and the QA test creator skill can understand and use it.

## Decisions & constraints

- Lives in `integration/README.md`.
- The QA test creator skill reads this as its primary reference.
- Must be kept in sync as primitives/presets evolve.

## Key files

- `integration/README.md` (new)

## Acceptance criteria

- Documents `run.sh` subcommands with examples
- Lists all primitives and presets with signatures and descriptions
- Explains `IntegrationEnv` dataclass fields
- Explains log file structure and how to inspect results
- Shows how to write a new test with a minimal example
- Documents env isolation model (what HOME/XDG_CONFIG_HOME point to)
