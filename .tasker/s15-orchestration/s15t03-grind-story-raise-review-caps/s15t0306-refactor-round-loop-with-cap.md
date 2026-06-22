---
id: s15t0306
slug: refactor-round-loop-with-cap
status: done
---

# Refactor: round-loop-with-cap-break skeleton duplicated across three phases

## Refactor side-task
- depth: 1
- origin: s15t0301 — refactor finding "round-loop-with-cap-break skeleton duplicated across three phases"

## Goal

Apply the deferred refactoring surfaced while processing s15t0301.
- location: .claude/workflows/grind-story.js:728 (reviewPhaseA), :788 (refactorPhaseB), :919 (verifyStep)
- severity: nit

All three phases share the same control skeleton: `for (let round = 1; round <= CAP; round++) { ...; if (round === CAP) break/handle; await fixAgent }`. The diff just swapped the single CAP for VERIFY_CAP/REVIEW_CAP across these, making the parallel structure more visible. This is closer to incidental similarity than true duplication (each body differs substantially in finding-routing logic), so unification risks a thin/over-general abstraction — flagging only for awareness, not action.

## Suggested fix

Leave as-is unless a fourth capped loop appears; if it does, consider a small `runCappedRounds(cap, fn)` driver where fn returns a done/continue signal. Not recommended now — the per-phase bodies diverge enough that extraction would obscure more than it dedups.
