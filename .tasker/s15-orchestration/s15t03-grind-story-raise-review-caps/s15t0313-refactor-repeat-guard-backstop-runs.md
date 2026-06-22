---
id: s15t0313
slug: refactor-repeat-guard-backstop-runs
status: in-review
---

# Refactor: Repeat-guard backstop runs after the pick agent has already moved the re-served task to in-progress

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "Repeat-guard backstop runs after the pick agent has already moved the re-served task to in-progress"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:1046-1053
- severity: nit

The pick prompt moves the chosen item to in-progress before returning, but the firstRepeat backstop then breaks the loop on an already-attempted id without resetting that status, leaving a re-served task in-progress on break. This mirrors pre-existing behavior (the old single-item guard had the same gap), so it is not a regression, but the new group-aware path inherits and slightly widens it. Resetting status via the set-status verb (or even logging it) touches the loop's break flow and tracker interaction — structural work to seed, not a local cleanup.

## Suggested fix

On a repeat-guard break, note in the log that the re-served id(s) may have been left in-progress by the pick agent, or have the loop reset them via the set-status verb before breaking. At minimum document the known gap in the backstop comment.
