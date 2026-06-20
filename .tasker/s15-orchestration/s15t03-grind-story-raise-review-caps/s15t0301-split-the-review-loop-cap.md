---
id: s15t0301
slug: split-the-review-loop-cap
status: pending
---

# Split the review-loop cap from the verify cap

## Goal

The two review-phase convergence loops run up to 10 rounds while Verify's tox-fix loop still caps at 5. Observable in the loop bounds and the round-log/escalation strings (`round N/10` for review phases, `round N/5` for verify).

## Decisions & constraints

- Introduce `REVIEW_CAP = 10` and use it for both `reviewPhaseA` (the fix-now loop) and `refactorPhaseB` (the apply-now loop). Keep `CAP = 5` for `verifyStep` (the tox-fix loop). Rationale: the review loops are convergence loops that benefit from more room; verify gates tox and has different semantics, so it should not be loosened.
- Every log line and escalation detail that names a cap must reflect the cap of *its own* loop — e.g. Review-A's `round ${round}/${CAP}` and its `${CAP}-round cap` escalation text must read 10, while verify's reads 5. Do not leave any review-phase message interpolating the verify cap.

## Edge cases

- The fix-now cap-open escalation message in `reviewPhaseA` (`${openFixNow.length} fix-now finding(s) still open at the ${CAP}-round cap`) and the `escalations.push({... detail: ... after ${CAP} Review-A rounds})` must both report 10.
- Refactor-B's cap-reached log (`Refactor-B cap reached for ${pick.taskId} ...`) is bounded by `REVIEW_CAP`; its loop is best-effort (no convergence failure), behavior unchanged otherwise.

## Key files

- `.claude/workflows/grind-story.js` — `const CAP` near the orchestration section; `reviewPhaseA`, `refactorPhaseB`, `verifyStep`.

## Acceptance criteria

- `reviewPhaseA` loops `round <= 10`; its fix-now-still-open escalation/halt path triggers only after 10 rounds and its messages say 10.
- `refactorPhaseB` loops `round <= 10` and its cap log says 10.
- `verifyStep` still loops `round <= 5` and its messages say 5.
- `uv run tox` (all envs) green.
