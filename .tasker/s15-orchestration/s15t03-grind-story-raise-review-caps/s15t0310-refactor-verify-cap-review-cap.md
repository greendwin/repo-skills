---
id: s15t0310
slug: refactor-verify-cap-review-cap
status: done
---

# Refactor: VERIFY_CAP / REVIEW_CAP split lands with no test asserting the new caps

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "VERIFY_CAP / REVIEW_CAP split lands with no test asserting the new caps"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:609
- severity: minor

The single CAP=5 was split into VERIFY_CAP=5 and REVIEW_CAP=10 and rethreaded across ~10 loop bounds and messages, plus a new 'PREFER refactor tasks' selection rule — none of which has a behavior-level test. Because grind-story.js ends in a top-level return and is loaded as a function body, these are module-level consts the existing extraction seam cannot reach. (Dedup: merges the two tests-lens findings on the untested cap split and the untested refactor-before-feature ordering; strongest severity kept.) Wiring a new constant-extraction seam (or a phase->cap helper) through the harness is structural test-infra work beyond a local edit, and the reporters themselves frame it as a documented-coverage-gap decision — so it is routed to delayed for a deliberate call rather than forced in place.

## Suggested fix

If feasible, expose the caps (or a small pure phase->cap helper) through the same extraction seam used for `normalizePick` and assert `VERIFY_CAP === 5 && REVIEW_CAP === 10 && REVIEW_CAP > VERIFY_CAP` and that each loop references the intended one; otherwise record in the task that the cap split is constant-only and intentionally untested so the gap is a documented decision.
