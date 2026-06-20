---
id: s15t0202
slug: phase-a-implement-review-loop
status: done
---

# Phase A: implement review loop with triage and fix-reconverge

## Goal

After the `tdd` implement step (Slice 1), run the `code-reviewer` roster in parallel, triage the findings via a structured-output agent, fix `fix-now` findings with `tdd`, and re-review — converging when no `fix-now` remains or at a 5-round cap. This is `dev-loop` steps 3a–3d re-encoded as workflow phases.

## Decisions & constraints

- **Lenses run in parallel** within the phase (`parallel()` of the roster lenses resolved from the context pack: `general`, `tests`, `performance`). Each is a read-only review agent that returns findings; it never writes the tree.
- **Finding contract as a schema** — every lens returns `{title, location, severity (blocker/major/minor/nit), rationale, suggested-fix, lens}`. Pass a JSON schema to `agent()` so findings come back validated.
- **Triage is its own structured-output `agent()`**, never the JS. The bucketing `dev-loop` reserves for "orchestrator only" can't be done by judgment-free JS, so a triage agent dedups by `location`+description overlap and buckets into `fix-now` / `deferred-to-refactor` / `out-of-scope`. Rules it's given: `fix-now` = change introduced it AND threatens delivered behavior (correctness/security/data-loss/missing-test/ADR-violation); when uncertain → `deferred-to-refactor`; never silently drop, never scope-creep.
- **Fix-reconverge:** spawn a `tdd` agent for the `fix-now` findings (failing test → green), then re-run lenses + triage. Repeat until no `fix-now` or **5 iterations**; at the cap, record it (hard escalation handling is Slice 5).
- **`deferred-to-refactor` findings are carried forward** to Phase B (Slice 3), not dropped.
- Reviewers read the current `git diff` against the branch base ref themselves for currency; only `tdd` writes the tree.

## Edge cases

- Empty `code-reviewer` roster in config → skip Phase A entirely (mirror `dev-loop`'s empty-roster behavior).
- A lens agent dies / returns null → filter it out, continue with the rest (don't fail the round).
- 5-round cap hit with `fix-now` still open → record for Slice 5's escalation; do not commit red.
- Duplicate findings across lenses → triage dedups before bucketing.

## Key files

- `.claude/workflows/grind-story.js` — extend the per-subtask cycle from Slice 1 with Phase A between implement and tox-gate.

## Acceptance criteria

- On a subtask whose initial implementation has a deliberate behavior bug, the loop surfaces it via a lens, triages it `fix-now`, fixes it with `tdd`, and re-converges green before committing.
- Lens agents run concurrently (single `parallel()`), each returning schema-valid findings.
- A pure-quality finding (no behavior threat) is bucketed `deferred-to-refactor` and visibly carried into Phase B, not fixed in Phase A.
- The fix-reconverge loop stops at 5 iterations and records the open `fix-now` rather than looping forever.
- An empty `code-reviewer` roster causes Phase A to be skipped with a logged note.
