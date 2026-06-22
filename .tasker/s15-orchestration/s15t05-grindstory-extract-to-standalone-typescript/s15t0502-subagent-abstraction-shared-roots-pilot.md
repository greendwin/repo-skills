---
id: s15t0502
slug: subagent-abstraction-shared-roots-pilot
status: pending
---

# Subagent abstraction + shared roots + pilot invocation

## Goal

Introduce the `Subagent<A,R>` abstraction (`defineSubagent`) and the shared `schemas/` and `domain/` roots, then extract exactly one subagent — `pick` (the canonical `parse`) — into `invocations/pick.ts` with a co-located, passing `invocations/pick.test.ts`. Build stays green. This pilots the whole invocation pattern on one agent before fanning out in the next slice.

## Decisions & constraints

- **`Subagent<A,R>` is a single functional instance** bundling: name, prompt builder, schema, label, a pure `parse`, and `run`. Replaces today's scattered free functions + constants. `defineSubagent` is the factory in `src/subagent.ts`.
- **`parse` is the pure raw→typed boundary.** `parse(raw: any): R` normalizes the agent's `any` result into a typed shape, collapsing today's scattered guards (`arr(obj,key)`, `(x && x.y) || {}`, the body of `normalizePick`). It must be **pure** — no logging, no side effects. Today's over-serve logging inside `normalizePick` moves into `run` (or the caller), not `parse`. This is what makes it unit-testable.
- **Shared roots established here:** `src/schemas/` holds shared JSON-schema fragments (start with `PICK_ITEM`, `PICK_SCHEMA`); `src/domain/` holds shared TS types (start with `PickResult` = `{done, kind: 'refactor'|'feature', items: WorkItem[], overserved?, stalled?}` and `WorkItem`).
- **Tests via `node:test` through `tsx`**, co-located as `*.test.ts` next to the module. Production bundle entry is `index.ts`'s graph only, so test files never reach the artifact.
- **`pick` is the pilot** because its `normalizePick` is the richest parse (enforces FEATURE_GROUP_CAP=1 / REFACTOR_GROUP_CAP=5, computes over-serve/stalled). Wire `index.ts`'s monolith to call the new `pick` Subagent instead of the inline functions, keeping behavior identical.

## Edge cases

- `normalizePick`'s cap enforcement and over-serve detection are behavior that must be preserved exactly — split the pure normalization (→ `parse`) from the `log()` of over-serve (→ `run`).
- Feature picks carry exactly one item; refactor picks 1–5 — `parse` must uphold this shape invariant.
- Keep `index.ts` building green throughout: the monolith still owns everything except `pick`.

## Key files

- `~/grind-story/src/subagent.ts` (new — `defineSubagent`/`Subagent<A,R>`)
- `~/grind-story/src/schemas/pick.ts` (new — `PICK_ITEM`, `PICK_SCHEMA`)
- `~/grind-story/src/domain/work.ts` (new — `PickResult`, `WorkItem`)
- `~/grind-story/src/invocations/pick.ts` (new — Subagent instance + prompt + pure `parse`)
- `~/grind-story/src/invocations/pick.test.ts` (new — `parse` unit tests, ported from the current pick `*.test.mjs` assertions)
- `~/grind-story/src/index.ts` (rewire to use the `pick` Subagent)

## Acceptance criteria

- `defineSubagent` produces a `Subagent` whose `parse` is pure (callable with a plain object, no globals/logging) and returns the typed `PickResult`.
- `invocations/pick.test.ts` covers: normal feature pick (1 item), refactor group (≤5), over-serve trimming, stalled/empty cases — all passing under `node:test`+`tsx`.
- The built `grind-story.js` still picks identically to before (same ordering, caps, over-serve logs).
- `tsc --noEmit` + tox `js` green.
