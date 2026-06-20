---
id: s15t0324
slug: refactor-grind-story-js-continues
status: pending
---

# Refactor: grind-story.js continues to grow past the 1k-line threshold (1100 -> 1185)

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "grind-story.js continues to grow past the 1k-line threshold (1100 -> 1185)"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js (whole file, now 1185 lines)
- severity: nit

The lens flags files past 1k lines as a structural smell. The file was already over the line (1100) before this change and this diff adds ~85 more (helpers, the extracted `processItem`, and several multi-line explanatory comment blocks). The single module now bundles schema definitions, every prompt-builder, the orchestration loop, all phase functions, and the report renderer. This is pre-existing rather than introduced here, but the change pushes it further without splitting; the project rule is to address even pre-existing structural issues.

## Suggested fix

Split the module along its existing comment-banner seams — e.g. extract the prompt builders/schemas into a sibling module and the report renderer into another, leaving the orchestration loop and phase functions in grind-story.js — so each file sits well under 1k lines. Defer if a split would break the harness's 'load as a function body ending in top-level return' loading contract; if so, file it as a tracked follow-up rather than leaving it unflagged.
