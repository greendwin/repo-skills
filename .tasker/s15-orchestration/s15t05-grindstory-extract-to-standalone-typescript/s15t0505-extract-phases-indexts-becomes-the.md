---
id: s15t0505
slug: extract-phases-indexts-becomes-the
status: pending
---

# Extract phases; index.ts becomes the thin driver

## Goal

Complete the two-tree layout: extract one module per phase under `phases/` plus a `phases/helpers.ts` for shared phase logic, reducing `index.ts` to just `export const meta` + the driver loop. Delete the text-slice test seam (`_extract-fn.mjs`) and all remaining `*.test.mjs`, porting their still-live assertions to co-located `*.test.ts`. Build stays green.

## Decisions & constraints

- **One module per phase** under `src/phases/`: `setup`, `bootstrap`, `pick`, `implement`, `review-a`, `refactor-b`, `file-side-tasks`, `verify`, `status-commit`. Each exports a phase function with signature `(ctx, outcomes, item)` and imports the Subagents it needs from `invocations/`.
- **`phases/helpers.ts`** holds the shared phase helpers: `runLensRound` (shared by Review-A and Refactor-B), `roundTag`, `phaseCap` (PHASE_CAPS = {Verify:5, 'Review-A':10, 'Refactor-B':10}), and the bounded-round loop. Distinct from `failure.ts` (run-level control flow).
- **`index.ts` is the thin driver:** constructs `RunContext` + `Outcomes`, runs the `while (processed.length < GUARD_MAX)` pick loop calling phases in order, branches on pick `kind` (feature vs refactor group), and returns `outcomes.render(...)`.
- **Text-slice seam fully retired:** delete `_extract-fn.mjs` and every remaining `*.test.mjs`; port any assertions not already re-homed in slices 2–4 into co-located `*.test.ts`. Supersedes s15t0326 (make import()-able) and s15t0309 (brace-walker limitation).
- Behavior-preserving: phase ordering, caps, the feature-vs-refactor-group branch, the full refactor-group pipeline (apply → Review-A → Refactor-B → file-side-tasks → Verify → commit), and all failure/drop semantics stay identical.

## Edge cases

- `runLensRound` is shared by two phases with different lens rosters and caps — parameterize, don't duplicate.
- The refactor-group path runs the full pipeline and uses min-member-depth for side-task filing — keep that in the right phase module.
- Some `*.test.mjs` assertions may already be covered by `*.test.ts` ported in earlier slices — don't duplicate; only port what's still unique.
- `index.ts` must not retain any phase logic — if a helper is shared by phases it goes to `phases/helpers.ts`; if it's run-level control flow it's already in `failure.ts`.

## Key files

- `~/grind-story/src/phases/{setup,bootstrap,pick,implement,review-a,refactor-b,file-side-tasks,verify,status-commit}.ts` (new)
- `~/grind-story/src/phases/helpers.ts` (new — `runLensRound`, `roundTag`, `phaseCap`, bounded-round loop)
- `~/grind-story/src/phases/*.test.ts` (new where logic warrants)
- `~/grind-story/src/index.ts` (reduced to meta + driver loop)
- DELETE: `~/grind-story/.claude/workflows/_extract-fn.mjs` + all `~/grind-story/.claude/workflows/*.test.mjs`

## Acceptance criteria

- `index.ts` contains only `export const meta`, the driver loop, and ctx/outcomes construction — no phase bodies, no inline prompts/schemas.
- Each phase is its own module with the `(ctx, outcomes, item)` signature; shared helpers live in `phases/helpers.ts`.
- `_extract-fn.mjs` and all `*.test.mjs` are deleted; the test suite is entirely co-located `*.test.ts` and passes under `node:test`+`tsx`.
- The built `grind-story.js` is behaviorally identical to pre-refactor (same phases, caps, branches, failure handling).
- `tsc --noEmit` + tox `js` green.
