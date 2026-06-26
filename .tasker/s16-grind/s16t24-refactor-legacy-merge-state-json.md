---
id: s16t24
slug: refactor-legacy-merge-state-json
status: pending
---

# Refactor: Legacy merge-state.json never cleaned up for users who don't resume a merge

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Legacy merge-state.json never cleaned up for users who don't resume a merge"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:1036 (_resolve_active_merge calls _cleanup_legacy_merge_state)
- severity: minor

_cleanup_legacy_merge_state runs only from _resolve_active_merge, i.e. only on `merge --continue` / `--abort`. An upgrading user who had a stale merge-state.json but never resumes a deferred merge keeps the orphaned config artifact on disk indefinitely. This is already captured as pending task s16t16, but the current change is what strands the file. Does not threaten delivered behavior (frozen stale artifact) and is explicitly tracked elsewhere.

## Suggested fix

Invoke the best-effort unlink from a path hit by every `skills merge` invocation (e.g. at the start of the merge command), not only the resume boundary; or accept and explicitly defer to s16t16.
