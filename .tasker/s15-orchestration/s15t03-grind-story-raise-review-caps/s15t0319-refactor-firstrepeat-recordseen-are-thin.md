---
id: s15t0319
slug: refactor-firstrepeat-recordseen-are-thin
status: pending
---

# Refactor: firstRepeat / recordSeen are thin identity wrappers over one-line Set operations

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "firstRepeat / recordSeen are thin identity wrappers over one-line Set operations"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:119-131
- severity: nit

`firstRepeat` is `items.find((it) => seen.has(it.taskId)) || null` and `recordSeen` is a two-line `for...seen.add`. Wrapping trivial Set/array idioms in named functions adds indirection for almost no abstraction gain. However the finding itself concludes the seam is currently defensible: it exists precisely because grind-story.js cannot be imported, and the new repeat-guard.test.mjs suite binds to these helpers through that seam. Inlining them at the loop call sites would delete the seam those tests rely on and force re-testing the guard through the loop — a structural trade-off tied to the same module-split decision above, not a clean local win. Routed as a side-task seed to be weighed alongside the file split.

## Suggested fix

If kept, that is defensible for the test seam; if the team prefers less indirection, inline both at the single call site (loop at :1052/:1057) as `pick.items.find((it) => seen.has(it.taskId))` and `pick.items.forEach((it) => seen.add(it.taskId))`, and test the guard behavior through the loop rather than the micro-helpers. Do not grow more such wrappers as grouping lands. Best decided together with the grind-story.js module split.
