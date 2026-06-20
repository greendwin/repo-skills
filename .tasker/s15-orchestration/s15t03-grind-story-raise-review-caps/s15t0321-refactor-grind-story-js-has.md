---
id: s15t0321
slug: refactor-grind-story-js-has
status: pending
---

# Refactor: grind-story.js has grown past 1k lines and the new per-item pipeline makes a module split natural

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "grind-story.js has grown past 1k lines and the new per-item pipeline makes a module split natural"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:1 (whole file, now ~1177 lines)
- severity: minor

The lens explicitly targets files past 1k lines. This diff did not create the overflow but it extracts a clean, self-contained per-item pipeline plus pure helpers (normalizePick/firstRepeat/recordSeen/resolveMarker) — exactly the seam along which the file could be decomposed. The `.claude/workflows/_extract-fn.mjs` harness (confirmed present, used by grind-story.normalize-pick.test.mjs and grind-story.repeat-guard.test.mjs) only exists because the whole file is loaded as a single top-level function body and 'cannot be imported directly', forcing the pure helpers to be sliced out by brace-walking. Real module boundaries would let tests import the helpers directly. This is genuinely valuable but big: it creates new ESM modules, rewires the entry file's top-level-return shape, and retires the shared test harness — blast radius well beyond the current task. Bias to delayed.

## Suggested fix

File as a follow-up side-task: split the pure side-effect-free helpers (normalizePick, firstRepeat, recordSeen, resolveMarker, findingSignature, buildSideTaskDescription) into an importable ESM module (e.g. grind-story.lib.mjs) that grind-story.js imports, and have the test suites import those directly — retiring the brace-walking extractFunction harness. As a second follow-up, lift the per-item phase functions into their own module so the orchestration file drops below 1k lines, preserving the entry file's required top-level-return shape for only the orchestration shell.
