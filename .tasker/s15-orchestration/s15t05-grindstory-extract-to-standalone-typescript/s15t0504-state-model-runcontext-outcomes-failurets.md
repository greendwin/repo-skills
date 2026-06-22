---
id: s15t0504
slug: state-model-runcontext-outcomes-failurets
status: pending
---

# State model: RunContext + Outcomes + failure.ts

## Goal

Introduce the state model: a frozen `RunContext` (immutable config), an `Outcomes` collector that owns the ~13 mutable accumulators behind intent-named methods and a `render`, and a `failure.ts` holding the run-level control-flow primitives. Rewire `index.ts` to construct both and drive the loop with bare `instanceof`. `Outcomes` is unit-tested. Build stays green.

## Decisions & constraints

- **`RunContext` (frozen) in `src/context.ts`** holds immutable config: storyId, packPath, baseRef, maxDepth, totalSideTaskCap, resolved review/refactor lenses, and any other run-constant config. Constructed once in `index.ts`, passed read-only to phases.
- **`Outcomes` collector in `src/outcomes.ts`** owns the ~13 accumulators currently loose at module scope: `processed`, `deferredFindings`, `delayedFindings`, `outOfScopeFindings`, `droppedRefactors`, `droppedSideTasks`, `escalations`, `filedSignatures`, `filedSideTasks`, `residualFindings`, `capSuppressed`, `sideTaskCount`, `seen`. Expose intent-named methods (`deferFinding`, `dropSideTask`, `recordCommit`, `escalate`, ...) instead of raw `.push`. The accumulators are **typed** (absorbs s15t0404's "type the accumulators" goal).
- **`report()` becomes `outcomes.render(ctx, failure)`** — the final report rendering moves onto the collector.
- **`failure.ts`** holds `Halt`, `SkipItem` (sentinel classes) and `failConvergence` (builds a `Halt`). These are run-spanning control flow, kept distinct from phase helpers. The loop site dispatches with bare `instanceof Halt` / `instanceof SkipItem`; the old `classifyLoopError`/`loopAction` indirection is **retired**.
- **Phase signature becomes `phase(ctx, outcomes, item)`** (phases are extracted in the next slice; here `index.ts`'s still-inline phase code is adapted to read/write through `ctx`/`outcomes`).
- Behavior-preserving: the rendered report and all accumulation semantics (dedupe via `filedSignatures`/`findingSignature`, cap suppression, side-task counting) stay identical.

## Edge cases

- `seen`/`firstRepeat`/`recordSeen` (loop-stall detection) move into `Outcomes` or stay as pure helpers it uses — keep the stall semantics intact.
- Failure semantics differ by kind: original/feature subtask non-convergence → `Halt` (dirty tree preserved); side-task (depth ≥ 1) → drop + continue. `failConvergence` + the loop's `instanceof` dispatch must preserve this split exactly.
- The grouped-refactor cancellation paths (whole-group fail → dedicated cancellation commit; single-member drop before group commit) record through `Outcomes` methods — keep them faithful.
- `render` must produce the same sections as today's `report()` (task→sha→origin map, dropped side-tasks, out-of-scope, escalations, cap-suppressed, residual).

## Key files

- `~/grind-story/src/context.ts` (new — `RunContext`)
- `~/grind-story/src/outcomes.ts` (new — `Outcomes` + `render`)
- `~/grind-story/src/outcomes.test.ts` (new — accumulator/method + render unit tests)
- `~/grind-story/src/failure.ts` (new — `Halt`, `SkipItem`, `failConvergence`)
- `~/grind-story/src/index.ts` (construct ctx+outcomes; loop uses bare `instanceof`; drop `classifyLoopError`/`loopAction`)

## Acceptance criteria

- `RunContext` is frozen (mutation throws/no-ops) and carries the full immutable config set.
- `Outcomes` exposes intent-named, typed methods; no raw module-level accumulator arrays remain in `index.ts`.
- `outcomes.render(ctx, failure)` reproduces today's report output for representative runs.
- The loop dispatches failures via `instanceof Halt`/`instanceof SkipItem`; `classifyLoopError`/`loopAction` are gone.
- `outcomes.test.ts` covers the key mutations (defer/drop/escalate/record-commit, dedupe, cap suppression) — passing.
- `tsc --noEmit` + tox `js` green.
