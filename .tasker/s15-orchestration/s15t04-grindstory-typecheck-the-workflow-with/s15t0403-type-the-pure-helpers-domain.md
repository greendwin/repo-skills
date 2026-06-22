---
id: s15t0403
slug: type-the-pure-helpers-domain
status: pending
---

# Type the pure helpers + domain typedefs under @ts-check

## Goal

`// @ts-check` is enabled at the top of `grind-story.js`, the inline JSDoc `@typedef`s exist beside their matching `*_SCHEMA` constants, and the pure helper functions plus the `.test.mjs`/`_extract-fn.mjs` files are fully typed and green under `tsc`. The pure helpers are the test-covered substance of the workflow, so they type cleanly first, on top of the already-proven wrapper+tsc pipeline.

## Decisions & constraints

- **Domain typedefs inline in `grind-story.js`, beside their `*_SCHEMA`.** Author JSDoc `@typedef`s for the domain shapes — `Finding` (mirrors `FINDING_ITEM`), `PickItem` (mirrors `PICK_ITEM`), the `{done, kind, items}` pick result, the triage buckets (`TRIAGE_SCHEMA`/`REFACTOR_TRIAGE_SCHEMA`), and the structured agent-result shapes — co-located with the matching schema literal so the two cannot drift. They travel with the body into the generated wrapper; the function body cannot `import`, so they must be inline (not a sidecar `.d.ts`). `globals.d.ts` stays runtime-API-only. *Rejected: a separate `.d.ts` sidecar (body can't import; becomes ambient globals that drift from the schema literals).*
- **Type the pure helpers fully (the helper half of the typing decision).** Annotate, with `@param`/`@returns` against the new typedefs: `normalizePick`, `parseDepthMarker`, `buildSideTaskDescription`, `findingSignature`, `phaseCap`, `firstRepeat`, `recordSeen`. These hold the logic that can actually be wrong and are exactly what the `.test.mjs` suites exercise. The accumulator arrays and the pick-result cast are deferred to Slice 4.
- **Keep the helpers behavior-identical.** This is a typing-only change — no logic edits. The existing `grind-story.normalize-pick.test.mjs`, `grind-story.group-pick.test.mjs`, `grind-story.phase-cap.test.mjs`, `grind-story.repeat-guard.test.mjs` must stay green unchanged.
- Honor CLAUDE.md: no task ids in code comments (the typedefs/JSDoc are comments — keep them id-free).

## Edge cases

- `_extract-fn.mjs` slices a helper by name and `eval`s it in isolation; the typedefs the helper references live in `grind-story.js`, not in the sliced fragment — confirm the slicing still works at runtime (typedefs are comments, so they are dropped by the brace-walk slice; verify the slice boundaries are unaffected by added JSDoc blocks).
- `@ts-check` may surface latent issues in the helpers (e.g. a possibly-undefined access) — fix by tightening types/guards, never by weakening a real check or adding `@ts-ignore`.
- The `.test.mjs` files may need `@param`/cast annotations where they construct partial fixtures against the new typedefs — keep them honest (the fixtures intentionally omit fields to test defaulting).

## Key files

- `.claude/workflows/grind-story.js` — add `// @ts-check`, inline `@typedef`s beside the `*_SCHEMA`, annotate the seven pure helpers.
- `.claude/workflows/grind-story.normalize-pick.test.mjs`, `grind-story.group-pick.test.mjs`, `grind-story.phase-cap.test.mjs`, `grind-story.repeat-guard.test.mjs` — annotate as needed to stay strict-clean.
- `.claude/workflows/_extract-fn.mjs` — annotate if strict requires.

## Acceptance criteria

- `// @ts-check` is on in `grind-story.js` and `uv run tox -e js` is green (both `tsc` and `node --test`).
- The seven pure helpers carry `@param`/`@returns` against inline typedefs; each typedef sits next to its `*_SCHEMA`.
- All four `.test.mjs` suites pass unchanged (no behavior edits to helpers).
- Introducing a deliberate shape mismatch in a helper call (temporary) is caught by `tsc` — proving the annotations are load-bearing.
