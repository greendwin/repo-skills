---
id: s15t0303
slug: batched-refactor-pick-group-up
status: pending
---

# Batched refactor pick (group up to 5)

## Goal

When picking refactors, the pick agent bundles up to 5 small, local, non-overlapping refactor tasks into one `items` array; feature picks stay single. Builds directly on Slice 2's uniform items contract.

## Decisions & constraints

- Grouping is **refactor-only**: `kind:'feature'` picks always carry exactly one item; only `kind:'refactor'` picks may carry 1–5 items.
- The pick agent judges feasible work size from each candidate side-task's description (title/location/severity/suggested-fix/rationale) — there is no mechanical pre-implementation size signal. Guidance to encode in the prompt: bundle refactors that are small, local, and non-overlapping (prefer same-area, non-conflicting changes); stop adding when the combined change looks too big to land+review cleanly in one pass.
- Hard cap of 5 enforced regardless of the agent's judgment.
- Pick still sets **every** grouped member in-progress atomically before returning; the loop's `seen`/re-pick guard records all member ids.

## Edge cases

- Fewer than 5 eligible refactors → group is however many qualify (1–4).
- Already-attempted ids (`excludeIds`) are excluded from group membership.
- A single eligible refactor → group of one (valid).
- The agent must not mix feature tasks into a refactor group, and must not exceed 5.

## Key files

- `.claude/workflows/grind-story.js` — `pickPrompt` (grouping guidance + cap), `PICK_SCHEMA` (already array from Slice 2; tighten descriptions for grouping), the `seen` bookkeeping in the main loop.

## Acceptance criteria

- A refactor pick with several small eligible side-tasks returns multiple items (≤ 5).
- A feature pick never returns more than one item.
- All returned member ids are set in-progress and recorded in `seen`.
- The cap of 5 is never exceeded even when more refactors are eligible.
- `uv run tox` (all envs) green.
