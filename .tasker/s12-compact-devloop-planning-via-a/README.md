---
id: s12
slug: compact-devloop-planning-via-a
status: pending
---

# Compact /dev-loop planning via a non-interactive /dev-tdd fork

## Context

`/dev-loop`'s Step 2 (Plan and approve) makes the orchestrator explore the codebase, read CONTEXT.md + ADRs, and synthesize the tracer-bullet slice list inline — all in the main context window. This raw exploration pollutes the orchestrator's context. Goal: delegate exploration + plan synthesis to a non-interactive subagent so the orchestrator holds only the distilled plan + a compact digest, keeping its context lean while preserving the mandatory planning gate and the "only the writer touches the tracked tree" invariant.

Artifacts: new `~/.claude/skills/dev-tdd/SKILL.md`; rewritten `~/.claude/skills/dev-loop/SKILL.md` (Steps 1–3a); deleted `~/.claude/agents/tdd.md`. Note these live under `~/.claude`, not the repo-skills tree.

## Decisions

- **Delegate exploration + slice synthesis, keep task-id resolution in the orchestrator** — the orchestrator's context should hold only the distilled plan + digest, never raw exploration. Step-1 task-id resolution stays with the orchestrator because it needs ids for status transitions anyway.
- **Fork `/tdd` into a non-interactive `/dev-tdd`** rather than bolting a mode onto `/tdd`. *Rejected: adding a "plan-only" mode to `/tdd` (muddies its interactive identity and the "only tdd writes" invariant); using the generic `Plan`/`Explore` agents (no knowledge of the tracer-bullet slice contract or task-tracker verbs).* `/tdd` stays pristine for human/standalone use.
- **`/dev-tdd` owns BOTH `plan` and `execute` modes** — `/dev-loop` never calls `/tdd` at all. *Rationale: interactivity is the problem in execute mode too (the planning/readiness/grill-me preamble dev-loop suppresses with "skip review"); one fork removes all suppression hacks and gives dev-loop a single clean subagent contract.*
- **No dedicated agent wrapper for `/dev-tdd`** — `/dev-loop` spawns a `general-purpose` agent with a one-line prompt: "invoke `/dev-tdd` in {plan|execute} mode with these inputs." *Rejected: a dedicated `dev-tdd` agent — its only durable value (stable name, model pin, framing) can all live in the skill itself; a second wrapper duplicating the skill cuts against the compaction goal.* The full non-interactive/return-data/approval-granted contract lives in the `/dev-tdd` skill.
- **Delete the orphaned `tdd` agent wrapper** (`~/.claude/agents/tdd.md`) — its sole consumer was dev-loop delegation, now gone. *Rejected: keeping it "just in case" (YAGNI; orphaned artifact duplicating the `/tdd` skill). Re-create if a future need arises.*
- **`/dev-tdd` references `/tdd`'s craft sidecars** (`tests.python.md`, `mocking.python.md`, `deep-modules.md`, `interface-design.md`, etc.) rather than copying them. *Rejected: full copy (craft drifts in two places).* `/dev-tdd`'s own SKILL.md holds only modes + return contracts + non-interactive overrides — zero craft duplication. Extracting shared craft into neutral sidecars is the clean end-state if it gets messy.
- **Explicit `mode:` keyword in the spawn prompt** (`plan` / `execute`), not inferred. Plan-mode produces the digest; execute-mode consumes it plus its one slice. The digest is the contract surface between the two modes so neither re-explores from zero.
- **Orchestrator passes task-id only; plan-mode `/dev-tdd` reads the task body** and distills it into the slice list + digest. *Rationale: the task body (goal, acceptance criteria, parent decisions) is exactly the bulk that pollutes orchestrator context.* `/dev-tdd` already has the `read-task` verb from `/tdd`.
- **Plan-mode returns `{slice list, digest, blocking open-questions, assumptions}`** — ambiguity is handed back as DATA, never via an interactive `/grill-me` (a subagent can't gate on the user). True blockers → explicit open-questions; minor judgment calls → visible assumptions inline in the plan the user approves.
- **Approval loop revises inline from the digest**, re-spawning plan-mode only when a change needs facts outside the digest (e.g. "also handle subsystem X you didn't look at"). *Rejected: always re-spawn (loses the cheap common case); revise-only-inline (can't cover out-of-digest requests).*
- **`--skip-plan` skips the approval WAIT but cannot override blocking open-questions** — true blockers still reach the user; auto-approve resumes once resolved. *Rationale: `--skip-plan` means "don't make me click approve," not "proceed on genuinely undecided design"; matches the mandatory-gate invariant which relaxes the wait, never correctness.*
- **Digest = four fixed sections**: `## Files`, `## Domain`, `## Constraints`, `## Decisions` (prose within each). *Rejected: freeform prose (informal parsing); per-slice fragments (re-fragments the exploration the digest is meant to consolidate).*

## Open questions

- None outstanding — all grill questions resolved.

## Out of scope

- Refactoring `/tdd`'s shared craft into neutral provider-agnostic sidecars (the (3) end-state of the content-reuse decision) — only do this if referencing `/tdd`'s sidecars proves messy.
- Changes to the review-lens rosters or `docs/agents/dev-loop.md` config.
- Any change to `/tdd`'s own interactive behavior (it stays as-is for humans).

## Subtasks

- [x] [s12t01](s12t01-author-devtdd-skill-with-plan.md): Author /dev-tdd skill with plan mode
- [x] [s12t02](s12t02-add-execute-mode-to-devtdd.md): Add execute mode to /dev-tdd
- [ ] [s12t03](s12t03-rewrite-devloop-steps-13-to.md): Rewrite /dev-loop Steps 1-3 to delegate planning to /dev-tdd
- [ ] [s12t04](s12t04-delete-the-orphaned-tdd-agent.md): Delete the orphaned tdd agent wrapper
