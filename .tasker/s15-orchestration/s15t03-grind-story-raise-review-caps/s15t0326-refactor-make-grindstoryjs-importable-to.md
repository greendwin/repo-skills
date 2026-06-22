---
id: s15t0326
slug: refactor-make-grindstoryjs-importable-to
status: pending
---

# Refactor: make grind-story.js import()-able to retire the text-slice test seam

## Refactor side-task
- depth: 1
- origin: s15t0314 — refactor finding "classifyLoopError + loopAction getters add a seam layer that exists only to work around a text-slice test harness"

## Goal

Durable fix for the `_extract-fn.mjs` text-slice test seam. Today the `*.test.mjs` suites slice named top-level `function` declarations out of `grind-story.js` and eval them in isolation because the file ends in a top-level `return` (it is loaded by the harness as a function body) and so cannot be `import()`-ed. That seam forces self-contained helpers (no free variables) and brace-clean bodies, and it drove two indirections that exist only to be reachable through it:
- the `loopAction` getters on the `Halt`/`SkipItem` sentinels plus the standalone `classifyLoopError` (introduced so the loop's skip/halt/rethrow decision is seam-testable), and
- the brace-walker + async-prefix slicing in `_extract-fn.mjs`.

- location: .claude/workflows/grind-story.js (Halt/SkipItem sentinels + classifyLoopError; the top-level `return`), .claude/workflows/_extract-fn.mjs
- severity: minor

## Suggested fix

Guard the trailing top-level `return` (and any other top-level side effects) so `grind-story.js` can be `import()`-ed as an ESM module exporting its pure helpers, then have the test suites import the real functions instead of text-slicing them. With real imports available, delete the `loopAction` getters + `classifyLoopError` and let `runGroup` classify via `instanceof Halt`/`instanceof SkipItem` directly, and retire the brace-walker/async-prefix slicing in `_extract-fn.mjs`. This deletes the whole text-parsing seam and its downstream indirections rather than rearranging them. Subsumes the deferred durable-fix half of s15t0309 (the brace-naive limitation).
