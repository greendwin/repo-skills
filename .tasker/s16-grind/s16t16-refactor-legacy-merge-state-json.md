---
id: s16t16
slug: refactor-legacy-merge-state-json
status: in-progress
---

# Refactor: Legacy merge-state.json cleanup never fires for upgrading users who don't resume a merge

## Refactor side-task
- depth: 2
- origin: s16t08 — refactor finding "Legacy merge-state.json cleanup never fires for upgrading users who don't resume a merge"

## Goal

Apply the deferred refactoring surfaced while processing s16t08.
- location: src/repo_skills/cli/_merge.py:47-52 (_cleanup_legacy_merge_state, called only from _merge_continue and _merge_abort)
- severity: nit

The fix only unlinks on `merge --continue` / `merge --abort`. A user who upgraded and then never resumes an old merge keeps the orphaned file indefinitely. The subtask scope explicitly sanctions this ('on merge --continue/--abort (or a one-time load)'), so it is acceptable; the cleanup is merely narrower than 'any user'. This is a completeness/quality nit that does not threaten delivered behavior — a stale orphan file is harmless cruft. Extends scope beyond the current subtask, so routed as a seed rather than applied in place.

## Suggested fix

Optionally also call `_cleanup_legacy_merge_state()` at the start of `_merge_start`/`_merge_retarget` (or once in the shared `_run_branch_merge` entry) so any merge invocation reaps the stale file. If intentionally scoped to resume paths, no change needed.
