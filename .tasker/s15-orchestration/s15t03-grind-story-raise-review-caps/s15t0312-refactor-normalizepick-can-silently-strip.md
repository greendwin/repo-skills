---
id: s15t0312
slug: refactor-normalizepick-can-silently-strip
status: pending
---

# Refactor: normalizePick can silently strip an item the pick agent already moved to in-progress, leaving a task stranded

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "normalizePick can silently strip an item the pick agent already moved to in-progress, leaving a task stranded"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:106-118 (normalizePick) consumed at lines 1040-1045
- severity: minor

The pick prompt instructs the agent to move every returned item to in-progress BEFORE returning. If a non-done pick yields zero usable items after the taskId filter, normalizePick collapses to `{done:true,items:[]}` and the loop logs the generic "No pending work items remain." and breaks — stranding any task already flipped to in-progress with no diagnostic. (Dedup: merges the two general-lens findings describing the same silent-collapse stranding; strongest severity kept.) The author's own rationale calls this acceptable for the slice; it is degenerate-path defensive handling that does not threaten the delivered single-item, well-formed path, and a distinct warning involves loop/log-flow changes better seeded as a side-task than forced in.

## Suggested fix

When a non-done raw pick yields zero usable items, log a distinct warning (e.g. "pick returned no usable items despite done=false — terminating; check for a task left in-progress") instead of the generic "No pending work items remain.", so a stranded in-progress task is observable.
