---
id: s09t06
slug: qa-test-creator-skill
status: pending
---

# QA test creator skill

## Goal

`.claude/skills/qa-test-creator/SKILL.md` — a project-level skill that instructs the agent to design and write new integration test scenarios using the documented primitives and presets.

## Decisions & constraints

- Separate from QA triage skill — different cognitive tasks.
- Reads `integration/README.md` for available building blocks.
- Accepts either a free-form scenario description or a QA triage report finding reference.
- Can be invoked standalone ("write a test for detached skill edge case") or chained from triage ("write a regression test for finding #3").
- Project-level, flat under `.claude/skills/`.

## Key files

- `.claude/skills/qa-test-creator/SKILL.md` (new)

## Acceptance criteria

- Skill prompt instructs reading `integration/README.md` before generating tests
- Generates test files using existing primitives/presets from the framework
- Accepts a scenario description or a QA report finding reference as input
- Produces tests that follow the project's integration test conventions (subprocess invocation, log capture, `IntegrationEnv`)
- Skill file is valid and discoverable by Claude Code
