---
id: s15t0314
slug: refactor-for-const-item-of
status: pending
---

# Refactor: `for (const item of pick.items) await processItem(item)` comment overclaims correctness for future multi-item 

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "`for (const item of pick.items) await processItem(item)` comment overclaims correctness for future multi-item groups"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:1057-1066
- severity: minor

The comment says grouping "flows through unchanged" and the catch wrapper handles SkipItem/Halt. In this slice items.length===1 so it is correct. But once a group carries >1 item (Slice 3), a `SkipItem` thrown by item N triggers `continue`, abandoning items N+1.. — which the pick agent has ALREADY moved to in-progress and which are ALREADY in `seen`, silently stranding work. This is a latent cross-slice hazard whose real resolution (per-item vs per-group skip semantics) is Slice 3 design work; flagging it now as a side-task seed is the right routing rather than altering this slice's single-item behavior.

## Suggested fix

Add a caveat to the comment, e.g. "NOTE: a SkipItem mid-group currently abandons the remaining items of the group (they are already in-progress + in `seen`); Slice 3 grouping must decide per-item vs per-group skip semantics before items can exceed one."
