---
id: s15t0318
slug: refactor-grind-story-js-has
status: pending
---

# [SUPERSEDED→s15t05] Refactor: split grind-story.js >1k lines (now done as the s15t05 module extraction)

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "grind-story.js has crossed the 1k-line threshold the lens flags"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js (1177 lines)
- severity: minor

The file is now 1177 lines, past the lens's explicit 1k-line watch line. It bundles several distinct concerns in one module body: schema definitions, prompt-string builders, the per-item pipeline (processItem and its phase helpers), and the top-level driver loop. The new processItem extraction is a good step (it lifted the loop body into a named pipeline), but the module keeps accreting and the function-body-with-trailing-return shape is what forces the awkward brace-walking test harness in the first place. The finding itself frames this as a follow-up (not blocking this slice); the split touches module structure broadly and changes how the harness loads the file, so it is a side-task seed rather than an in-place change.

## Suggested fix

As a follow-up (not blocking this slice), split the pure, testable pieces — normalizePick, firstRepeat/recordSeen, resolveMarker, findingSignature, the schema constants — into a sibling module that grind-story.js imports, so they become directly importable (retiring extractFunction entirely) and the driver file shrinks back under the threshold.
