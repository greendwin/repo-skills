---
id: s15t0317
slug: refactor-pick-schema-carries-a
status: pending
---

# Refactor: PICK_SCHEMA carries a `kind` field with no consumer (scaffolding ahead of its slice)

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "PICK_SCHEMA carries a `kind` field with no consumer (scaffolding ahead of its slice)"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:101-117 (PICK_SCHEMA / normalizePick) and the pick prompt at :449-455
- severity: minor

`kind` is added to the schema, defaulted in normalizePick, taught to the pick agent in the prompt, and tested — yet the comment at :191-198 admits the loop's refactor/feature split is still driven entirely by resolveMarker's depth marker, so `kind` is never read after normalization. A normalized/validated field with zero consumers is dead-weight structure that invites readers to hunt for a branch that does not exist, and risks the agent's `kind` silently diverging from the marker-derived classification with no detection. Resolving this is a scope judgment (defer the field to its consuming slice, or wire a cross-check invariant) that reaches across schema, prompt, and the per-item pipeline — beyond a local behavior-preserving collapse, so it is routed as a side-task seed.

## Suggested fix

Either defer the `kind` schema field, prompt instructions, and normalizePick defaulting to the slice that actually branches on it (keeping this change to the items-array reshaping the loop genuinely needs now), or add a single assertion/log in processItem that cross-checks `pick.kind` against resolveMarker's depth so the carried field is at least exercised as an invariant rather than carried inert.
