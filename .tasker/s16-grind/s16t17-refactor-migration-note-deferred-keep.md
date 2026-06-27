---
id: s16t17
slug: refactor-migration-note-deferred-keep
status: in-progress
---

# Refactor: Migration note ('deferred keep-source merges must be re-run') lives only in a code comment, not surfaced to us

## Refactor side-task
- depth: 2
- origin: s16t08 — refactor finding "Migration note ('deferred keep-source merges must be re-run') lives only in a code comment, not surfaced to users"

## Goal

Apply the deferred refactoring surfaced while processing s16t08.
- location: src/repo_skills/cli/_merge.py:48-51 (_cleanup_legacy_merge_state comment)
- severity: nit

A user with a deferred --keep-source merge persisted pre-upgrade silently loses that intent. The reviewer notes the project has no CHANGELOG, so this is consistent with conventions and explicitly acceptable. Surfacing the migration is a UX/quality enhancement, not a correctness defect or ADR violation; delivered behavior (cleanup of the stale artifact) is intact. The suggested warning is new user-facing behavior beyond the subtask, so routed as a seed; if pursued it must follow ADR 0001's `[yellow]Warning:[/yellow]` shape.

## Suggested fix

Acceptable as-is given no changelog convention; if desired, emit a one-time `[yellow]Warning:[/yellow]` (per ADR 0001) when a stale merge-state.json is actually found (unlink returned a file that existed) noting any deferred keep-source merge must be re-run.
