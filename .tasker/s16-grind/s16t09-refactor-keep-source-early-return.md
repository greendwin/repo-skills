---
id: s16t09
slug: refactor-keep-source-early-return
status: in-review
---

# Refactor: keep-source early-return pattern repeated across three finalize sinks

## Refactor side-task
- depth: 1
- origin: s16t03 — refactor finding "keep-source early-return pattern repeated across three finalize sinks"

## Goal

Apply the deferred refactoring surfaced while processing s16t03.
- location: src/repo_skills/cli/_merge.py:145-147 (_write_retarget_manifest), 583-585 (_retarget_in_sync), 1081-1085 (_finalize)
- severity: minor

Three sites now share the identical keep-source guard: `if keep_source: console.print(_merged_still_tracking(...)); return`. The `_finalize` copy was rewritten in this diff to match this exact shape (the old version did persisted-state clearing). All three resolve old_source then print the same 'still tracking' line and bail before the manifest write. The branch-name refactor made `_finalize` converge on the same shape as the two retarget sinks, so the parallelism is now true (same helper, same effect) rather than incidental — a good moment to unify so a future change to keep-source messaging/semantics touches one place, not three.

## Suggested fix

Note in review only (read-only lens). The three already funnel through `_merged_still_tracking`; the remaining duplication is the surrounding guard+return. Options: (a) leave as-is — the guard bodies differ slightly (`_finalize` tolerates `old_source=None`, the others take a guaranteed-non-None `old_source`), so unifying risks over-abstracting; or (b) if convergence is intended, hoist a tiny `_emit_keep_source(skill_name, target_name, old_source) -> None` that prints `_merged_still_tracking(...)` and have each caller do `if keep_source: _emit_keep_source(...); return`. Given the differing nullability contracts, severity is minor — flag for awareness rather than mandate.
