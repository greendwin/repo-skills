---
id: s14t04
slug: side-task-filing-from-delayed
status: pending
---

# Side-task filing from `delayed` and depth-bounded re-queue

## Goal

Turn Phase B's `delayed` findings into tracked refactoring side-tasks that the queue loop picks up and processes like any other subtask, bounded by `maxDepth` and a total-count backstop. This is what makes "continue from the beginning until all subtasks finished" actually generate and consume work.

## Decisions & constraints

- **Side-tasks are flat children of the story** (siblings of original subtasks), created via the `create-subtask` verb with `parent = <story-id>` — NOT nested under the spawning subtask. Deep nesting was rejected as brittle.
- **Depth + linkage baked into the description** as a parseable marker block:
  ```
  ## Refactor side-task
  - depth: 1
  - origin: s08t12 — thermo finding "collapse duplicate dispatch branches"
  ```
  Original subtasks have no such block → treated as **depth 0**. A side-task spawned while processing a depth-`d` subtask gets `depth: d+1`. The `origin:` line records the spawning subtask id + finding title (feeds the report's task→commit→origin map).
- **Queue loop parses the marker on each re-query** so side-tasks are selected and run through the full Phase A + Phase B cycle exactly like originals.
- **`maxDepth = 2` (default).** Spawning is gated by depth: a subtask already at depth 2 does NOT file its `delayed` findings — it reports them as residual instead. (Depth-2 subtasks are still fully implemented/refactored/committed; only their *children* are suppressed.)
- **Total-side-task cap backstop** — a hard ceiling on side-tasks filed per run; when reached, stop filing and `log()` the suppression (default ~30, tunable). Prevents runaway since thermo is never fully satisfied.
- Side-tasks are born `pending`; their `in-progress`/`in-review` transitions happen when the loop later picks them (Slice 1 machinery).

## Edge cases

- A `delayed` finding duplicates an already-filed side-task (re-surfaced on a later round) → dedupe against existing story children (by origin/finding) before filing, so the loop converges instead of re-filing forever.
- Depth marker malformed/absent on a side-task someone hand-edited → default to treating depth as 0 but `log()` the anomaly.
- Total cap reached mid-round → file none of the remainder, report them as suppressed-by-cap.
- maxDepth raised by the caller (param) → deeper grinding still bounded by the total cap.

## Key files

- `.claude/workflows/grind-story.js` — add side-task filing after Phase B triage; extend the queue-pick to parse the depth marker and the spawn-gate to check depth + total cap.

## Acceptance criteria

- A `delayed` finding from an original (depth-0) subtask is filed as a flat child of the story with `depth: 1` and a correct `origin:` line, then picked up and fully processed (Phase A+B+commit) on a later iteration.
- A subtask at `depth: 2` does not file side-tasks — its `delayed` findings appear as residual in the report.
- Re-surfaced duplicate `delayed` findings are not re-filed; the loop converges and terminates when no `pending` remain.
- Hitting the total-side-task cap stops further filing and logs the suppression.
