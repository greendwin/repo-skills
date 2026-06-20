---
id: s15t0307
slug: refactor-reviewphasea-and-refactorphaseb-duplicate
status: pending
---

# Refactor: reviewPhaseA and refactorPhaseB duplicate the entire lens-round/triage/cap-break loop skeleton

## Refactor side-task
- depth: 1
- origin: s15t0301 — refactor finding "reviewPhaseA and refactorPhaseB duplicate the entire lens-round/triage/cap-break loop skeleton"

## Goal

Apply the deferred refactoring surfaced while processing s15t0301.
- location: .claude/workflows/grind-story.js:724-778 and :785-845 (reviewPhaseA / refactorPhaseB)
- severity: minor

Both phase functions share the same structural skeleton: a `for (round = 1; round <= REVIEW_CAP; round++)` loop, a `runLensRound(...)` call, an empty-findings early break with a roundTag log, an `agent(triagePrompt...)` call producing `buckets`, `arr(buckets, ...)` extraction, a global findings-push, a 'no actionable bucket' early break with a roundTag log, and a `round === REVIEW_CAP` terminal branch. Unifying it would let the shared cap, round counter, and break/log wording evolve in one place. Routed to delayed (not apply-now) because this is genuinely valuable but BIGGER structural work: extracting a parameterized loop helper that owns control flow across two phase functions and threads phase-specific callbacks is not a trivially-local behavior-preserving collapse, and the duplication is pre-existing rather than introduced by this diff.

## Suggested fix

Extract a `runReviewLoop({phase, lenses, lensPrompt, lensLabel, triagePrompt, triageSchema, bucketSpec, onRound})` helper that owns the `for (round...REVIEW_CAP)` loop, the empty-findings break, the triage call, bucket arr() extraction, and the roundTag logging; have reviewPhaseA and refactorPhaseB supply only their phase-specific bucket names and per-round action (fix vs apply) via callbacks, so the loop scaffold and cap live in exactly one place.
