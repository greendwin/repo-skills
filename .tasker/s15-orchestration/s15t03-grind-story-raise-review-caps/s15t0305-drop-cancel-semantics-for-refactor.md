---
id: s15t0305
slug: drop-cancel-semantics-for-refactor
status: pending
---

# Drop/cancel semantics for refactor tasks

## Goal

Dropped refactor tasks are moved to tasker's cancelled state (not merely reset), across all three drop scenarios, while feature-task failure still Halts the run.

## Decisions & constraints

- Cancel verb: `mcp__tasker__cancel_task` (tasker's native cancel transition) for any dropped refactor task.
- **Whole-group convergence failure** (group apply can't converge, Review-A fix-now still open at the review cap, or tox red at the verify cap — every group member is depth ≥ 1): `git reset --hard` discards the combined change (reverting in-progress `.tasker` edits), then cancel **every** member, then make a **dedicated cancellation commit** (e.g. `chore: cancel non-converging refactor side-tasks`) so the cancelled status is committed and never leaks into an unrelated next item's commit. Then continue with the next pick (SkipItem semantics). A reset that doesn't leave a clean tree still escalates to Halt.
- **Single member dropped within an otherwise-green group**: cancel that member **before** the group commit so its `.tasker` cancelled edit rides in the normal group commit (no extra commit).
- **All members dropped by apply (empty refactor diff)**: short-circuit — skip Review-A/Refactor-B/Verify entirely, cancel all members, record the dedicated cancellation commit, continue.
- **Feature-task failure unchanged**: feature subtasks are depth 0, so a convergence failure still Halts the run (tree left dirty for inspection); only refactor tasks are dropped+cancelled.
- Report: dropped/cancelled members surface in the existing dropped-side-tasks section with their reason; the dedicated cancellation commit appears as its own entry where commits are tracked.

## Edge cases

- Reset-not-clean after a whole-group failure → Halt (don't build on a dirty tree), as today's side-task reset-failure path.
- A group where some members applied and some dropped, and the applied subset then fails convergence → whole-group failure path (reset + cancel all members, including the already-dropped ones).
- Empty-diff short-circuit must not run the verify/commit-of-source path — only the cancellation commit.
- Cancellation commit message carries no task ids (per CLAUDE.md).

## Key files

- `.claude/workflows/grind-story.js` — `failConvergence` (group cancel + dedicated cancellation commit on the reset path), the group-apply result handling (per-member cancel-before-commit), the empty-diff short-circuit in the loop body, a cancellation-commit prompt, `droppedSideTasks`/report wiring.
- `docs/agents/task-tracker.md` — confirm/resolve the cancel transition (note: the status-roles table currently lists pending/in-progress/in-review/done; cancellation uses `mcp__tasker__cancel_task` directly).

## Acceptance criteria

- A non-converging refactor group is reset, every member cancelled in tasker, and a dedicated cancellation commit is recorded before the run continues.
- A single dropped member in a green group is cancelled and its status edit rides the group commit (no separate commit).
- An all-dropped group short-circuits past review/verify, cancels all members, and records the cancellation commit.
- A failing feature subtask still Halts the run.
- `uv run tox` (all envs) green.
