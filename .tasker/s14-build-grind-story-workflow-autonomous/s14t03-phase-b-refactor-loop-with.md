---
id: s14t03
slug: phase-b-refactor-loop-with
status: done
---

# Phase B: refactor loop with duplication and thermo-nuclear lenses

## Goal

Once Phase A is green, run the `refactor-reviewer` roster (`duplication`, `thermo-nuclear`) in parallel, triage into `apply-now` / `delayed` / `out-of-scope`, apply `apply-now` refactorings behavior-preservingly via `tdd`, and loop until dry or 5 rounds. `delayed` findings are merely **collected** here (their filing as side-tasks is Slice 4).

## Goal context — this is `dev-loop` step 4 re-encoded, with the policy flip toward applying.

## Decisions & constraints

- **Refactor roster = `[duplication, thermo-nuclear]`**, resolved from the context pack (the `thermo-nuclear` lens delegates to the `thermo-nuclear-code-quality-review` skill — the review agent reads that skill prompt). No separate third thermo pass: thermo lives in this roster and side-tasks are born from triage buckets.
- **Lenses run in parallel**, same finding-contract schema as Phase A. Merge with the `deferred-to-refactor` findings carried from Phase A.
- **Triage agent buckets** into `apply-now` (improves quality, scoped to current task, local blast radius) / `delayed` (big refactor touching other systems or extending scope) / `out-of-scope` (unrelated, ADR-conflict). The triage prompt is **biased aggressively toward `delayed`**: route genuinely valuable structural work — rule-of-three duplication, real code-judo that *deletes* complexity — to `delayed`; reserve `out-of-scope` strictly for ADR-conflicts and noise.
- **Apply `apply-now` via `tdd`** under the green-test contract, behavior-preserving: may rework production code and fix test references to renamed/moved internals (same assertion, same expected value), but never change expected behavior to force a refactor through; a refactor `tdd` can't keep green is dropped and reported. `tdd` returns per-finding `{finding, outcome: applied/dropped, reason}`.
- **Loop until dry** (no new `apply-now`) or **5 iterations**.
- `delayed` findings are accumulated in JS for Slice 4; `out-of-scope` recorded for the report.

## Edge cases

- Empty `refactor-reviewer` roster → skip Phase B (mirror `dev-loop`).
- Lens/`tdd` agent returns null → filter, continue.
- An `apply-now` that `tdd` can't keep green → dropped + reported, not forced.
- Triage marks an ADR-conflicting "improvement" → `out-of-scope` (ADR wins), never `apply-now`/`delayed`.

## Key files

- `.claude/workflows/grind-story.js` — add Phase B after Phase A, before the tox-gate/commit.

## Acceptance criteria

- On a subtask with obvious local duplication, Phase B triages it `apply-now` and `tdd` collapses it while tests stay green.
- A large cross-cutting restructuring surfaced by the thermo lens is bucketed `delayed` and collected (not applied in place) for Slice 4.
- An ADR-conflicting suggestion is bucketed `out-of-scope`, not `delayed`.
- The refactor loop terminates at dry or 5 iterations; dropped refactors are reported with reasons.
- Empty refactor roster skips Phase B with a logged note.
