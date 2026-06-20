---
id: s15t0309
slug: refactor-extractfunction-brace-walker-is
status: pending
---

# Refactor: extractFunction brace-walker is a fragile test seam (no string/comment awareness)

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "extractFunction brace-walker is a fragile test seam (no string/comment awareness)"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.normalize-pick.test.mjs:21-34
- severity: minor

`extractFunction` counts raw `{`/`}` characters and ignores braces inside string literals, template literals, regexes, or comments. The extracted helpers contain none today, so the tests pass, but the seam mis-slices the moment an extracted function gains a `{` inside a string/template — yielding a confusing `new Function` syntax error. (Dedup: merges the two findings reporting the brace-naive walker; strongest severity kept.) The durable fix the reporter favors — making grind-story.js's pure helpers genuinely importable (guarding the trailing top-level `return` so the file can be `import()`-ed as ESM) — restructures the source module and the whole test seam, so it is a delayed side-task, not a local edit. A bare warning comment alone would not justify apply-now churn.

## Suggested fix

Refactor grind-story.js so the pure helpers are importable (e.g. guard the trailing top-level `return` so the file can be `import()`-ed as an ESM module), then import the real functions instead of text-slicing them; failing that, document the brace-naive limitation and keep the extracted helpers brace-clean.
