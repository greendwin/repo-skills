---
id: s15t0316
slug: refactor-top-level-js-suite
status: pending
---

# Refactor: Top-level JS suite test cannot detect a missing per-behavior suite (weak coverage guard)

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "Top-level JS suite test cannot detect a missing per-behavior suite (weak coverage guard)"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: tests/test_workflow_js.py:33-46
- severity: nit

`test_workflow_js_suite_passes` globs `*.test.mjs` and only asserts `>=1` suite exists and the aggregate run is green. If a future change deletes a suite (or a new public helper ships with no suite), tox stays green and the coverage loss is invisible. The lens's mandate is that every new public behavior has a behavior-level test; nothing enforces that the suites stay present. Pinning expected suite filenames or a minimum test count is a deliberate gate-hardening decision in the Python test harness that the grouping/test-infra slice should own, so it is seeded rather than forced here.

## Suggested fix

Either assert the expected suite filenames are present (e.g. `assert {p.name for p in test_files} >= {"grind-story.normalize-pick.test.mjs", "grind-story.repeat-guard.test.mjs"}`), or parse node's `--test-reporter` count and assert a minimum test count, so a vanished suite fails loudly.
