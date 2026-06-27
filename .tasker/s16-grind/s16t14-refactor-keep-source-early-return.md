---
id: s16t14
slug: refactor-keep-source-early-return
status: in-progress
---

# Refactor: keep-source early-return guard now truly parallel across three finalize sinks

## Refactor side-task
- depth: 2
- origin: s16t08 — refactor finding "keep-source early-return guard now truly parallel across three finalize sinks"

## Goal

Apply the deferred refactoring surfaced while processing s16t08.
- location: src/repo_skills/cli/_merge.py:1091-1095 (_finalize), 154-156 (_write_retarget_manifest), 592-594 (_retarget_in_sync)
- severity: minor

This diff rewrote the `_finalize` keep-source branch (it previously did persisted-state clearing) into the exact shape the two retarget sinks already use: `if keep_source: console.print(_merged_still_tracking(...)); return`. All three resolve an `old_source`, print the same 'still tracking' line, and bail before the manifest write. The parallelism is now true (same helper, same effect) rather than incidental, so a future change to keep-source messaging or bail semantics must be applied in three places. They already funnel through `_merged_still_tracking`; the remaining duplication is the surrounding guard+return.

## Suggested fix

If convergence is intended, hoist a tiny sink `def _emit_keep_source(skill_name: str, target_name: str, old_source: str | None) -> None` that calls `console.print(_merged_still_tracking(skill_name, target_name, old_source))`, and let each caller do `if keep_source: _emit_keep_source(...); return`. Note the nullability contracts differ — `_finalize` tolerates `old_source=None` while the retarget sinks pass a guaranteed-non-None value — so keep the param `str | None` and do not over-abstract the surrounding manifest logic. If the differing contracts make the helper feel forced, leaving as-is is acceptable.
