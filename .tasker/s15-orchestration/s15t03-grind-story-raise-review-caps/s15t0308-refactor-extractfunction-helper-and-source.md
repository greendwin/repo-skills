---
id: s15t0308
slug: refactor-extractfunction-helper-and-source
status: pending
---

# Refactor: extractFunction helper and source-loading preamble duplicated verbatim across the two .test.mjs suites

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "extractFunction helper and source-loading preamble duplicated verbatim across the two .test.mjs suites"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.normalize-pick.test.mjs:15-34 and .claude/workflows/grind-story.repeat-guard.test.mjs:16-34
- severity: major

Both new test files copy the same ~20-line block: the `here`/`source` file-loading preamble (readFileSync of grind-story.js) plus the entire `extractFunction(name)` balanced-brace extractor, byte-for-byte apart from one stray line. This is true duplication, not incidental similarity. The story explicitly expects more test files in later slices, so each future suite will re-clone the extractor and any fix must be applied in N places. (Dedup: merges five overlapping duplication/tests/thermo-nuclear findings reporting the same extractFunction+preamble copy across both suites; strongest severity kept.) Routed to delayed: introducing a new shared `_extract-fn.mjs` module, re-pointing both suites' imports, and confirming the Python gate's `*.test.mjs` glob still excludes the helper is structural work that adds a file and reaches the tox wiring — a side-task seed rather than a local behavior-preserving slice edit.

## Suggested fix

Extract a shared ESM helper, e.g. `.claude/workflows/_extract-fn.mjs`, exporting `extractFunction(name)` (and optionally `loadGrindStorySource()`). Each test file becomes `import { extractFunction } from './_extract-fn.mjs'` and `const normalizePick = extractFunction('normalizePick')`, deleting its private preamble+extractor. Verify the gate's `WORKFLOWS_DIR.glob('*.test.mjs')` still excludes the non-`.test.mjs` helper.
