---
id: s15t0302
slug: refactor-first-uniform-pick-contract
status: cancelled
---

# Refactor-first, uniform pick contract (single-item groups)

## Goal

Pick returns the new uniform `{ done, kind: 'refactor'|'feature', items: [...] }` shape and **prefers** marker-bearing refactor tasks over depth-0 feature tasks — still selecting one item per iteration. The loop body consumes `items`/`kind` as a group-of-one, with no behavior change to existing single-task processing. This is the tracer bullet that proves the new contract before grouping (Slice 3) and batched execution (Slice 4) land.

## Decisions & constraints

- "Refactoring task" = any task whose description carries the `## Refactor side-task` marker block (reuse `parseDepthMarker` / depth ≥ 1). Do not introduce a parallel classification.
- Preference: among eligible pending subtasks, select marker-bearing refactor tasks before depth-0 feature subtasks, so the run drains refactors first.
- `PICK_SCHEMA` becomes `{ done, kind: 'refactor'|'feature', items: [{taskId, title, description, isStory}] }`. In this slice `items` always has exactly one element (grouping arrives in Slice 3). Feature picks → `kind:'feature'`; refactor picks → `kind:'refactor'`.
- Pick atomically moves **every** returned item to in-progress before returning (one item here), so a mid-run crash leaves consistent tracker state.
- The loop body branches on `kind` and iterates `items`. The existing per-item machinery (`resolveMarker`, `seen`, `failConvergence` depth-split, `processed`) must keep working for a one-element group. The `seen`/re-pick guard adds every returned item id.
- Behavioral parity: a run with no refactor side-tasks present must process feature subtasks exactly as before (full pipeline, Halt-on-failure).

## Edge cases

- Degenerate story (no subtasks): the story task itself is the single feature item (`isStory:true`), as today.
- `excludeIds` / already-attempted exclusion still applies to every item.
- Empty pending set → `done:true`.

## Key files

- `.claude/workflows/grind-story.js` — `PICK_SCHEMA`, `pickPrompt`, the main `while` loop (pick consumption, `seen`, `resolveMarker`, the per-item `try` body).

## Acceptance criteria

- Pick returns `{done, kind, items}`; a refactor task is preferred over a pending feature task when both are eligible.
- All returned items are set in-progress by the pick step.
- The loop processes a one-item `items` array through the existing pipeline with unchanged outcomes for feature-only stories.
- `uv run tox` (all envs) green.
