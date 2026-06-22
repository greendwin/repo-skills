---
id: s15t0327
slug: refactor-extract-terminalloglinepick-so-the
status: pending
---

# Refactor: extract terminalLogLine(pick) so the stalled-vs-generic terminal log is seam-testable

## Refactor side-task
- depth: 1
- origin: s15t0312 — refactor finding "Loop's distinct `stalled` WARNING text is not behaviorally covered (reasonably untestable through current seam)"

## Goal

The main pick loop chooses between the distinct stalled warning ("pick returned no usable items despite done=false — terminating; a task may have been left in-progress by the pick agent (check the tracker).") and the generic "No pending work items remain." based on `pick.stalled`. The `stalled` MARKER is fully tested in normalize-pick.test.mjs (both directions), but the message SELECTION lives in the top-level `while` loop body, which the `_extract-fn.mjs` text-slice seam cannot reach. The two branches both `break`, so there is no behavior divergence — only operator-facing copy — which is why this was routed delayed rather than fix-now.

- location: .claude/workflows/grind-story.js (main pick loop terminal-pick branch)
- severity: minor

## Suggested fix

Extract a tiny pure, self-contained helper `terminalLogLine(pick)` that returns the correct terminal message string for a done/stalled pick, and have the loop call it. Then a seam test can extract `terminalLogLine` and assert a genuine done → the generic message and a stalled collapse → the distinct in-progress-warning message, pinning the genuine-done-vs-stalled choice without coupling to the loop. Note this becomes moot if the import()-ability follow-up lands first (the loop body would then be directly testable).
