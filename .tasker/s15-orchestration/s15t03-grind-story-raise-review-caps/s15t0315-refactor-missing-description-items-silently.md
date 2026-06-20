---
id: s15t0315
slug: refactor-missing-description-items-silently
status: pending
---

# Refactor: Missing-`description` items silently degrade a refactor pick to depth-0 feature processing

## Refactor side-task
- depth: 1
- origin: s15t0302 — refactor finding "Missing-`description` items silently degrade a refactor pick to depth-0 feature processing"

## Goal

Apply the deferred refactoring surfaced while processing s15t0302.
- location: .claude/workflows/grind-story.js:108-113 (normalizePick) and :1018 (resolveMarker)
- severity: nit

PICK_ITEM only requires `taskId`; `description` is optional and normalizePick defaults it to `''`. If the pick agent returns a refactor item but omits/empties its description, `resolveMarker` parses no marker => depth 0, so a side-task is processed as a depth-0 feature with no guard or log. Low likelihood, but the suggested guard requires threading `kind` onto the item and passing it into processItem — a contract/plumbing change that reaches across normalizePick and the loop, so it is a side-task seed rather than a local in-place edit.

## Suggested fix

Optionally log/warn when a kind='refactor' item resolves to depth 0 (description lacked a marker), e.g. inside processItem after resolveMarker; requires threading kind onto the item or passing it through.
