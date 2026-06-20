---
id: s15t0322
slug: refactor-skipitem-caught-outside-the
status: pending
---

# Refactor: SkipItem caught outside the per-item loop silently abandons the rest of a (future) group

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "SkipItem caught outside the per-item loop silently abandons the rest of a (future) group"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:1067-1077 (while-loop try/catch around `for (const item of pick.items) await processItem(item)`)
- severity: minor

`processItem` throws `SkipItem` to drop a single non-converging side-task and continue with the next work item. The catch is placed around the whole `for (const item of pick.items)` loop, so the `continue` jumps to the next outer `while` iteration (a fresh pick) — every still-unprocessed item in the current group is skipped even though `recordSeen` already added all their ids to `seen`. Those items are then permanently excluded and never processed. The adjacent comment asserts grouping 'flows through unchanged', but the SkipItem semantics are NOT preserved for a multi-item group. In this slice `items.length === 1` so there is no live defect, but the structure bakes in a wrong-granularity error handler that the very next slice (grouping) will silently inherit. Catching at the group level when the throw means 'skip THIS item' is logic at the wrong layer.

## Suggested fix

Move the SkipItem boundary inside the item loop so a skip only abandons the offending item, e.g. `for (const item of pick.items) { try { await processItem(item) } catch (e) { if (e instanceof SkipItem) continue; throw e } }`, leaving only `Halt` to be caught at the outer level. Alternatively have `processItem` return a skip signal instead of throwing across the loop boundary. Until grouping lands, at minimum soften the 'flows through unchanged' comment to call out that SkipItem currently aborts the whole group.
