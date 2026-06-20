---
id: s15t0101
slug: author-devtdd-skill-with-plan
status: done
---

# Fold mode: dispatch into /tdd; extract human routine to a sidecar

## Goal

Make `/tdd` the single dual-mode TDD skill. Invoked with **no mode** → today's interactive human flow (relocated to a `human-mode.md` sidecar); `mode: plan` → returns `{slice list, digest, open-questions, assumptions}`; `mode: execute` → drives red→green→refactor to green for one slice. `SKILL.md` stays agent-lean: craft pointers + mode dispatch + agent return contracts only; the rare human routine is read on demand from the sidecar.

This is the tracer bullet — it makes `/tdd` capable of everything `/dev-tdd` did, so later slices can repoint references and delete the fork.

## Decisions & constraints

- **One canonical TDD skill (collapse the fork).** Two near-identical TDD skills are confusing; `/tdd` is the single entry point. Craft-drift is already neutralized (`/dev-tdd` only references `/tdd`'s sidecars), so "one entry point" is the driver. *Reverses the earlier fork decision.*
- **Fold explicit `mode:` dispatch into `/tdd`.** No mode → interactive human path; `mode: plan` / `mode: execute` → non-interactive agent contract. The skill never infers mode; an absent/unknown `mode:` on a non-human spawn → stop and report. *This is the "bolt a mode onto /tdd" option originally rejected; chosen now because sidecar extraction makes it cheap.*
- **Hot path stays in SKILL.md; rare human routine moves to a sidecar.** A `SKILL.md` is loaded in full on every invocation; sidecars are read on demand. The subagent path is high-frequency (one plan + N execute + fix + refactor spawns per `/dev-loop` run), so `SKILL.md` keeps the common content: craft pointers + mode dispatch + the agent return contracts (digest, green-test, per-finding outcome) + the non-interactive overrides. The human-only routine (readiness check → grill-me → plan → approval gate → reactive escalation) moves to a sidecar (e.g. `human-mode.md`), read only when invoked with **no** mode. **Do NOT extract the mode dispatch or agent contracts** — those are the common path.
- **Human path stays first-class (dual-mode), byte-for-byte as today** — just relocated. *Rejected: a "subagent-first, human = thin adapter that decides how to adopt output" design — it softens `/tdd`'s deliberate approval/grill-me quality gate to agent discretion, which drifts.*
- **Contract moves verbatim.** The `mode: plan` / `mode: execute` sections, the four-section digest (`## Files` / `## Domain` / `## Constraints` / `## Decisions`), the green-test contract, and the per-finding `{finding, outcome, reason}` shape move unchanged from `/dev-tdd`. No redesign. The human "no mode" path never produces/consumes a digest — it plans + implements in one continuous flow as `/tdd` does now.
- Continue referencing `/tdd`'s craft sidecars (tests/mocking per language, deep-modules, interface-design) — no craft duplication.

## Edge cases

- `mode:` absent or unrecognized on a subagent spawn → stop and report; do not guess.
- Bare description (no task id) in `mode: plan`/`execute` → work from the description; do not read/require the task-tracker config.
- Missing `docs/agents/task-tracker.md` when a task-id IS given → halt and name the missing config (same contract as today's `/tdd`).
- Human (no-mode) invocation must behave exactly as current `/tdd` — verify the readiness/grill-me/approval/escalation flow survives the move to the sidecar intact.

## Key files

- Edit: `~/.claude/skills/tdd/SKILL.md` (add mode dispatch + agent contracts; trim the human routine out).
- New: `~/.claude/skills/tdd/human-mode.md` (the relocated interactive routine).
- Reference (do not edit): `~/.claude/skills/dev-tdd/SKILL.md` (source of the verbatim mode/contract content), `~/.claude/skills/tdd/` craft sidecars.

## Acceptance criteria

- `/tdd/SKILL.md` documents `mode: plan` and `mode: execute` dispatched by an explicit `mode:` keyword, plus the no-mode human path that defers to the sidecar.
- `mode: plan`'s documented output is exactly `{slice list, digest, open-questions, assumptions}` with the digest's four fixed headings; `mode: execute` documents slice + digest inputs, the green-test contract, and the per-finding `{finding, outcome, reason}` return.
- The non-interactive overrides (no grill-me, no approval wait, no clarification prompts) are stated for both modes.
- The interactive human routine lives in `human-mode.md` and is referenced (not duplicated) from `SKILL.md`; the no-mode path reproduces today's behavior.
- `SKILL.md` references the craft sidecars rather than restating them.
