---
id: s15t0404
slug: type-the-orchestration-accumulators-pickresult
status: pending
---

# Type the orchestration accumulators + pick-result cast

## Goal

The module-level accumulator arrays in `grind-story.js` carry element typedefs so every `.push` is shape-checked, the pick result is cast into `normalizePick` so its fields are typed at the one site where the shape materially flows on, the remaining `agent()` results stay `any` by design, and the full `js` env (`tsc` + `node --test`) is green. This is the highest-churn typing pass, deliberately last so it lands on an already-proven pipeline and already-typed helpers.

## Decisions & constraints

- **Type the accumulators fully (the accumulator half of the typing decision).** Annotate the module-level accumulator arrays with element typedefs so every `.push` is shape-checked: `processed`, `deferredFindings`, `delayedFindings`, `outOfScopeFindings`, `droppedRefactors`, `droppedSideTasks`, `escalations`, `filedSideTasks`, `residualFindings`, `capSuppressed` (and the `seen`/`filedSignatures` sets where they carry a meaningful element type). Use `@type {Array<...>}` JSDoc with typedefs (reuse the Slice 3 `Finding`/`PickItem` typedefs and add per-array row typedefs where the shape is bespoke, e.g. `{taskId, title, depth, reason}` for `droppedSideTasks`).
- **Cast only the pick result; leave other agent results `any`.** `agent()` returns `Promise<any>` by runtime contract. Add a single cast of the pick agent's result into `normalizePick` (`/** @type {RawPick} */ (await agent(...))` or equivalent) since that shape flows through the normalize/group machinery. Do NOT add casts at the other ~20 `agent()` call sites — that is ceremony around `any`-by-contract data that `tsc` cannot meaningfully verify, and was explicitly rejected. *Rejected: full casts at every agent call site.*
- **Typing-only, behavior-identical.** No orchestration logic changes. The wrapper's line alignment and the `any`-boundary choices are exercised here; if `@ts-check` surfaces a real latent bug in the orchestration, fix it under a test rather than silencing it — but the default expectation is pure annotation.
- Honor CLAUDE.md: no `@ts-ignore` where a real fix exists; no task ids in comments.

## Edge cases

- Some accumulators hold rows shaped differently from `Finding` (e.g. `{taskId, finding}`, `{taskId, title, depth, reason}`, escalation rows) — give each its own small typedef rather than forcing them into one shape.
- The `arr(obj, key)` defensive helper returns `any[]`-ish values off possibly-null agent results — ensure typing the accumulators does not force casts to spread through every `arr(...)` consumer (keep the `any` boundary at the agent-result edge).
- After this slice the wrapped file is the most heavily annotated — re-confirm `check-types.mjs` line alignment still holds and `tsc` runtime is acceptable.

## Key files

- `.claude/workflows/grind-story.js` — annotate the accumulator declarations and add the single pick-result cast.

## Acceptance criteria

- Every listed accumulator array has an element typedef; a deliberate wrong-shape `.push` (temporary) is caught by `tsc`.
- The pick result is cast exactly once into `normalizePick`; no new casts appear at other `agent()` call sites.
- `uv run tox` (all environments, including `js`) is green.
- `grind-story.js` remains a bare function body (runtime-loadable) with no behavior change — all `.test.mjs` suites pass.
