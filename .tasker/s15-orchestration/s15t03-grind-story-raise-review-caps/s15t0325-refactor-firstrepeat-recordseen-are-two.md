---
id: s15t0325
slug: refactor-firstrepeat-recordseen-are-two
status: pending
---

# Refactor: firstRepeat / recordSeen are two identity-thin helpers that always travel as a pair

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "firstRepeat / recordSeen are two identity-thin helpers that always travel as a pair"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:133-141 and call sites 1070,1075
- severity: nit

Both helpers are one-liners over the same `(items, seen)` pair and are only ever used together in the loop (find-a-repeat, then record-all). Each is a near-identity wrapper around `Array.find`/`Set.add`. Extracting them buys test seams (the .mjs suite targets them) but adds two named top-level functions plus two doc-comments for ~2 lines of logic; the indirection slightly thins the loop's readability since a reader must jump to two definitions to see it is just "is any id seen? else add all". Defensible as a tested seam, flagged only as a structural altitude nit.

## Suggested fix

If the test seam is the only driver, consider a single `checkAndRecord(items, seen)` that returns the first repeat (and records all only when none repeats), collapsing the two-call dance at lines 1070/1075 into one and halving the helper/comment surface. Otherwise leave as-is — the pair is harmless.
