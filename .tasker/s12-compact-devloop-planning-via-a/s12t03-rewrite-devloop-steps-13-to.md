---
id: s12t03
slug: rewrite-devloop-steps-13-to
status: pending
---

# Rewrite /dev-loop Steps 1-3 to delegate planning to /dev-tdd

## Goal

Rewrite the planning phase of `~/.claude/skills/dev-loop/SKILL.md` so the orchestrator no longer explores the codebase or synthesizes the slice list inline. Instead it delegates to plan-mode `/dev-tdd`, holds only the distilled plan + digest, and threads that digest into every execute-mode spawn.

## Decisions & constraints

- **Step 1 resolves task-ids only** (cheap; orchestrator needs ids for status transitions). The "Read CONTEXT.md and relevant ADRs" line and all codebase exploration move OUT of the orchestrator into plan-mode `/dev-tdd`.
- **New planning step:** orchestrator spawns a `general-purpose` agent with a one-line prompt — "invoke `/dev-tdd` in `mode: plan` with {task-id or bare description, CONTEXT/ADR pointers}". **No dedicated agent**; the full contract lives in the `/dev-tdd` skill. *(Rejected: a dedicated `dev-tdd` agent wrapper — redundant second artifact.)*
- **Orchestrator receives `{slice list, digest, open-questions, assumptions}`** and works from that distilled plan — never from raw exploration. It **holds the digest** for the run.
- **Approval loop revises inline from the digest**; it re-spawns plan-mode `/dev-tdd` only when a change needs facts outside the digest (e.g. "also handle subsystem X you didn't look at"). *(Rejected: always re-spawn; revise-only-inline.)*
- **`--skip-plan` skips the approval WAIT but cannot override blocking open-questions.** If plan-mode returns blockers, the orchestrator halts and surfaces them even under `--skip-plan`; auto-approve resumes once resolved. The mandatory-gate invariant relaxes the wait, never correctness.
- **Execute spawns (Steps 3a/3d/4c) thread the digest** plus the one slice into `mode: execute` `/dev-tdd`, replacing the current "spawn tdd subagent in execute mode / use skip-review path" wording. The orchestrator still never edits code or runs tests.
- Preserve the load-bearing invariants: planning gate mandatory; only `/dev-tdd` (the writer) touches the tracked tree under green tests; reviewers propose only.
- Surface plan-mode **assumptions** at the approval gate so the user approves them; route **blocking open-questions** to the user (optionally via `/grill-me`) before locking the plan.

## Edge cases

- Bare description (no task id): orchestrator passes the description to plan-mode and tells it "no tracked task".
- Plan revision needing out-of-digest facts → re-spawn plan-mode rather than guessing.
- `--skip-plan` + blocking open-questions → halt and surface (do not auto-proceed).

## Key files

- Edit: `~/.claude/skills/dev-loop/SKILL.md` — primarily Step 1, Step 2, and the spawn wording in Steps 3a/3d/4c. Roles table / invariants updated to name `/dev-tdd` as the spawned writer/planner.
- Reference: `~/.claude/skills/dev-tdd/SKILL.md` (the contract it must match); `docs/agents/dev-loop.md` (roster config, unchanged).

## Acceptance criteria

- Step 2 no longer instructs the orchestrator to explore the codebase or read CONTEXT/ADRs inline; that work is delegated to plan-mode `/dev-tdd` via a `general-purpose` spawn.
- The skill documents the orchestrator holding the digest and threading it into each `mode: execute` spawn.
- The approval loop documents inline-revise-from-digest with re-spawn only for out-of-digest changes.
- `--skip-plan` is documented as skipping the wait but not overriding blocking open-questions.
- All references to spawning a `tdd` subagent are replaced with spawning `general-purpose` + `/dev-tdd` (`plan`/`execute` modes); invariants remain intact.
