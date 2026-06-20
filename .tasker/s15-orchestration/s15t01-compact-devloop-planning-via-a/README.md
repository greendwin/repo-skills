---
id: s15t01
slug: compact-devloop-planning-via-a
status: done
---

# Collapse /dev-tdd back into a single canonical /tdd skill

## Context

`/dev-loop`'s planning phase originally made the orchestrator explore the codebase and synthesize the slice list inline, polluting its context. The first pass (this story's earlier subtasks) solved that by forking `/tdd` into a non-interactive `/dev-tdd` with `plan`/`execute` modes that the orchestrator delegates to. That worked, but left **two near-identical TDD skills**. This rework reverses the central fork decision: fold the mode machinery back **into** `/tdd` so there is one canonical TDD skill, while preserving every behavior the fork bought (non-interactive subagent contract, lean orchestrator context, the plan/execute digest handoff, and the mandatory human approval gate).

The original delegation goal is unchanged — the orchestrator still holds only a distilled plan + digest and never explores inline. Only the *hosting* skill changes: `/dev-loop` spawns `/tdd` (with a `mode:`) instead of `/dev-tdd`.

## Decisions

- **One canonical TDD skill (collapse the fork)** — two near-identical TDD skills are confusing; `/tdd` is the single entry point. The craft-drift argument is already neutralized (`/dev-tdd` only *references* `/tdd`'s sidecars — zero craft duplication), so "one entry point" is the real driver, not deduplication. *Reverses the earlier decision to fork `/tdd` into `/dev-tdd`.*

- **Fold explicit `mode:` dispatch into `/tdd`** — no mode → today's interactive human path; `mode: plan` / `mode: execute` → the non-interactive agent contract. *This is the "bolt a mode onto /tdd" option the fork originally rejected; chosen now because sidecar extraction (below) makes it cheap and keeps `/tdd`'s interactive identity intact.* The skill never infers mode; absent/unknown `mode:` on a non-human spawn → stop and report.

- **Keep the hot path in SKILL.md, move the rare human routine to a sidecar** — a `SKILL.md` is loaded in full on every invocation; sidecars are read on demand. The subagent path is high-frequency (one plan spawn + N execute + fix + refactor spawns per `/dev-loop` run), so anything in `SKILL.md` is paid on every spawn. Therefore `/tdd/SKILL.md` keeps the common content: craft pointers + mode dispatch + agent return contracts (digest, green-test, per-finding outcome). The rare human-only routine (readiness check → grill-me → plan → approval gate → reactive escalation) moves to a sidecar (e.g. `human-mode.md`), read only when `/tdd` is invoked with **no** mode. *Do not extract the mode dispatch or agent contracts — those are the common path.* Token win compounds with spawn count.

- **Human path stays first-class (dual-mode), not subagent-first** — the human flow is byte-for-byte what it is today, just relocated to the sidecar. *Rejected: a "subagent-first, human = thin adapter that decides how to adopt output" design — it softens `/tdd`'s deliberate approval/grill-me quality gate (the skill whose own description calls it "the standard workflow") to agent discretion, which drifts.*

- **Contract moves verbatim, no redesign** — the plan/execute split, the four-section digest (`## Files` / `## Domain` / `## Constraints` / `## Decisions`), the green-test contract, and the per-finding `{finding, outcome, reason}` shape move unchanged from `/dev-tdd` into `/tdd`. *Rejected: smuggling a contract redesign (collapsing modes, restructuring the digest) into a "merge two files" change.* The human "no mode" path never produces/consumes a digest — it plans + implements in one continuous flow as `/tdd` does now.

- **Spawn mechanism unchanged; `tdd` agent stays deleted** — `/dev-loop` still spawns a `general-purpose` agent with a one-line prompt ("invoke `/tdd` in `mode: {plan|execute}` with these inputs"); no dedicated wrapper. The deletion of the `tdd` agent wrapper is orthogonal to the fork and still holds. *Rejected: re-introducing a `tdd` agent now that `/tdd` is canonical — it re-creates the orphan-prone duplicate that was removed.* Only the skill name in the spawn prompt changes (`/dev-tdd` → `/tdd`).

- **Migrate every `/dev-tdd` reference back to `/tdd` in one coherent change** — a dangling reference to a deleted skill is latent breakage. Flip all references (preserving `mode:` where present) across `dev-loop`, `review-iter`, `fix-tests`, `setup-dev-loop` (SKILL.md, FORMAT.md, templates/generic.md, templates/claude-code.md, examples/dev-loop.md), and the in-repo `docs/agents/dev-loop.md`. Grep-confirm the exact set before editing.

- **Delete the `/dev-tdd` skill file** once its content is folded into `/tdd`.

## Open questions

- None outstanding — all grill questions resolved.

## Out of scope

- Any redesign of the digest, the plan/execute split, or the green-test / per-finding contracts (they move verbatim).
- Changes to `/tdd`'s actual interactive human behavior (it is relocated to a sidecar, not changed).
- Changes to the review-lens rosters or the *content* of `docs/agents/dev-loop.md` beyond the `/dev-tdd` → `/tdd` reference flip.
- Re-introducing any dedicated agent wrapper.

## Note

All edited skill files live under `~/.claude` (outside the repo tree); only `/work/docs/agents/dev-loop.md` is in-repo. These are markdown-only edits — `uv run tox` / TDD do not apply.

## Subtasks

- [x] [s15t0101](s15t0101-author-devtdd-skill-with-plan.md): Fold mode: dispatch into /tdd; extract human routine to a sidecar
- [x] [s15t0102](s15t0102-add-execute-mode-to-devtdd.md): Migrate every /dev-tdd reference back to /tdd
- [x] [s15t0103](s15t0103-rewrite-devloop-steps-13-to.md): Delete the /dev-tdd skill file
- [x] [s15t0104](s15t0104-delete-the-orphaned-tdd-agent.md): Delete the orphaned tdd agent wrapper
