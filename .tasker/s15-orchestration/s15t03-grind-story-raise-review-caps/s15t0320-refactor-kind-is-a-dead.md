---
id: s15t0320
slug: refactor-kind-is-a-dead
status: pending
---

# Refactor: `kind` is a dead/speculative field threaded through the whole pick contract but never consumed

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "`kind` is a dead/speculative field threaded through the whole pick contract but never consumed"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:116 (normalizePick), :213-229 (PICK_SCHEMA), :191-198 (PICK_ITEM block comment)
- severity: minor

Confirmed by grep: the only read of `.kind` anywhere in the file is line 116, the line that produces it; PICK_SCHEMA declares/enums it and the pick prompt (lines 449-450, 455) instructs the agent to set it, yet `processItem` re-derives the feature/refactor split from `resolveMarker`. So `kind` currently influences no behavior. HOWEVER, the PICK_SCHEMA comment (:191-198) and the shared context pack explicitly state `kind` is deliberately carried forward for the grouping/branching slice that arrives later and 'is not yet consumed' — it is intentional forward scaffolding, not an accident. Removing it reverses a deliberate design decision and the right move is to land `kind` atomically with its first reader, which is itself the future batched-refactor-pick slice. That is structural work scoped to ANOTHER (future) slice, not the current task, so it is a side-task seed rather than an in-place apply. No ADR conflict.

## Suggested fix

File as a side-task tied to the batched refactor-pick / branching slice: when that slice lands, either wire `kind` into its first real consumer or, if grouping ends up marker-driven, drop `kind` from PICK_SCHEMA, normalizePick's return shape, and the pick prompt so the field and its reader land together and cannot drift from the marker-derived split. Do NOT strip it speculatively in the current task, since that reverses the team's intentional forward scaffolding.
