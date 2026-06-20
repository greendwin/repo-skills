---
id: s15t0323
slug: refactor-kind-is-a-dead
status: pending
---

# Refactor: `kind` is a dead contract field — classification duplicated between the pick agent and `resolveMarker`

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "`kind` is a dead contract field — classification duplicated between the pick agent and `resolveMarker`"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:197-204 (PICK_SCHEMA comment), :449-461 (pickPrompt classification steps), :1022-1024 (`processItem` still derives depth/kind from the marker via resolveMarker)
- severity: minor

The pick prompt now asks the LLM to classify each eligible task as refactor (carries the `## Refactor side-task` marker) vs feature and emit `kind`, and the schema carries `kind`. But the loop never consumes `kind`: `processItem` re-derives the refactor/feature split deterministically from the same marker via `resolveMarker` (depth >= 1). So `kind` is, by the code's own comment, 'carried ... and is not yet consumed' — a currently-dead field whose value duplicates a classification the orchestrator already computes reliably from the marker. Delegating a deterministic, marker-based classification to the agent is logic in the wrong layer, and an unconsumed schema field is a thin/identity abstraction that can silently diverge from the code-side truth (e.g. agent says feature, marker says depth 1).

## Suggested fix

Either consume `kind` where the split is decided (replace the marker-derived branch in `processItem`/the depth-split with the agent's `kind`, validated against the marker) so the field earns its place, or drop `kind` from PICK_SCHEMA/PICK_ITEM and the pickPrompt classification prose for this slice and reintroduce it in the grouping slice that actually branches on it — keeping classification in one layer (code) until a consumer exists. If kept as a tracer, add a code-side assertion that `kind` matches `resolveMarker`'s depth so the duplicated classifications cannot drift unnoticed.
