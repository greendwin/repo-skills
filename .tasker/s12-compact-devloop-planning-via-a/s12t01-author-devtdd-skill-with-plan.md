---
id: s12t01
slug: author-devtdd-skill-with-plan
status: done
---

# Author /dev-tdd skill with plan mode

## Goal

Create a new skill at `~/.claude/skills/dev-tdd/SKILL.md` that, when invoked in `mode: plan`, explores the codebase, reads the task body, and returns a structured planning payload — fully non-interactive. This is the tracer bullet that proves the non-interactive fork pattern.

## Decisions & constraints

- **Fork of `/tdd`, non-interactive by design.** `/dev-tdd` exists specifically to be spawned by `/dev-loop`. It must NEVER invoke `/grill-me`, NEVER wait for user approval, and NEVER prompt for clarification. *(Rejected: bolting a plan mode onto interactive `/tdd` — muddies its identity and the "only tdd writes" invariant.)*
- **Plan-mode reads the task itself.** The orchestrator passes only a task-id (or a bare description); plan-mode `/dev-tdd` reads the task body and parent via the `read-task` verb (resolve `docs/agents/task-tracker.md`), because the task body is exactly the bulk that would otherwise pollute the orchestrator's context. Bare-description input → work from the description, do NOT read the task-tracker config.
- **Return payload (as data):** `{slice list, digest, blocking open-questions, assumptions}`.
  - Slice list: ordered tracer-bullet vertical slices, each with goal + acceptance criteria.
  - Ambiguity is handed back, never gated on the user: genuinely undecided design that changes the slices → **blocking open-questions**; minor judgment calls → **assumptions** recorded inline in the plan.
- **Digest = four fixed sections** (prose within each): `## Files`, `## Domain`, `## Constraints`, `## Decisions`. The digest is the contract surface that downstream execute-mode consumes, so its shape is fixed. *(Rejected: freeform prose / per-slice fragments.)*
- **Reference, don't copy, `/tdd`'s craft sidecars.** The SKILL.md owns only modes + return contract + non-interactive overrides; it points at `/tdd`'s existing sidecars for craft: `tests.python.md`, `mocking.python.md`, `tests.js.md`, `mocking.js.md`, `deep-modules.md`, `interface-design.md` (in `~/.claude/skills/tdd/`). Zero craft duplication. *(Rejected: full copy — craft drifts in two places.)*
- The readiness-check / grill-me machinery from `/tdd`'s Planning section becomes **report-not-invoke** here: it produces open-questions/assumptions instead of calling `/grill-me`.

## Edge cases

- Bare description (no task id): skip task-tracker read entirely.
- Missing `docs/agents/task-tracker.md` when a task-id IS given: halt and name the missing config (same contract as `/tdd`).
- Plan-mode produces blocking open-questions: just return them — do not attempt to resolve interactively.

## Key files

- New: `~/.claude/skills/dev-tdd/SKILL.md`
- Reference (read for shape, do not edit): `~/.claude/skills/tdd/SKILL.md` and its sidecars; `~/.claude/skills/dev-loop/SKILL.md` (for the slice/digest contract it expects).

## Acceptance criteria

- `~/.claude/skills/dev-tdd/SKILL.md` exists with valid frontmatter (`name: dev-tdd`, a description).
- It defines a `plan` mode whose documented output is exactly `{slice list, digest, blocking open-questions, assumptions}`, with the digest's four fixed section headings spelled out.
- It explicitly states non-interactivity (no `/grill-me`, no approval wait, no clarification prompts) and the read-task-by-id behavior.
- It references the `/tdd` craft sidecars by path rather than restating their content.
