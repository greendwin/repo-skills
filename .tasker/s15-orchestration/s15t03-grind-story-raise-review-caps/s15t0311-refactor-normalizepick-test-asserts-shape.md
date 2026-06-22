---
id: s15t0311
slug: refactor-normalizepick-test-asserts-shape
status: done
---

# Refactor: normalizePick test asserts shape but not the documented 'one-element in this slice' invariant for multi-item i

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "normalizePick test asserts shape but not the documented 'one-element in this slice' invariant for multi-item input"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.normalize-pick.test.mjs:78-86
- severity: minor

`normalizePick` passes through a multi-element `items` array unbounded, while the schema/prompt comments promise exactly one element in this slice. The tests only feed multi-element arrays whose extra elements are invalid (dropped by the taskId filter), so they never demonstrate two well-formed items. This pins behavior for the upcoming grouping slice rather than guarding behavior this slice relies on, so it is a forward-looking test-hardening seed best collected alongside the grouping work rather than expanded here.

## Suggested fix

Add a test feeding two well-formed items and assert the current pass-through semantics (e.g. `normalizePick({done:false, items:[{taskId:'a'},{taskId:'b'}]}).items.length === 2`), pinning the behavior so the later grouping slice has a guard.
