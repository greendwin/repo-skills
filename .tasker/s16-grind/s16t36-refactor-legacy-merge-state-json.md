---
id: s16t36
slug: refactor-legacy-merge-state-json
status: pending
---

# Refactor: Legacy merge-state.json cleanup only fires on --continue/--abort, never on a fresh merge

## Refactor side-task
- depth: 2
- origin: s16t10 — refactor finding "Legacy merge-state.json cleanup only fires on --continue/--abort, never on a fresh merge"

## Goal

Apply the deferred refactoring surfaced while processing s16t10.
- location: src/repo_skills/cli/_merge.py:50-53 (_cleanup_legacy_merge_state), called only from _resolve_active_merge (:1037)
- severity: minor

_cleanup_legacy_merge_state is invoked only via _resolve_active_merge, which runs on --continue/--abort. An upgrading user who never resumes a deferred merge (e.g. they abandon it or only ever start fresh merges) keeps the orphaned merge-state.json on disk indefinitely. The cleanup is best-effort housekeeping, so this is not data-corrupting, but the artifact lingers for the common case. (Tracked as s16t16/s16t24/s16t32.) Dedup: subsumes the nit reporting the same indefinite legacy-state touch on every resume. Explicitly enumerated as a separate backlog seam — route there, not in this slice.

## Suggested fix

Call _cleanup_legacy_merge_state() once on every merge entrypoint (also from _merge_start/_merge_retarget), or perform the unlink in a single shared merge-command boundary so it fires regardless of subcommand.
