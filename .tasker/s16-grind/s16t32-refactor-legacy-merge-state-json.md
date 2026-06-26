---
id: s16t32
slug: refactor-legacy-merge-state-json
status: pending
---

# Refactor: Legacy merge-state.json cleanup only fires on --continue/--abort, never on a fresh merge

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Legacy merge-state.json cleanup only fires on --continue/--abort, never on a fresh merge"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:50 (_cleanup_legacy_merge_state) — called only from _resolve_active_merge, reached only by _merge_continue/_merge_abort
- severity: nit

The whole point of this change is to retire the persisted merge-state.json mechanism. But the cleanup of the stale artifact is wired only into the deferred-resume entry point (_resolve_active_merge). An upgrading user who never resumes an old merge — the common case — keeps the orphaned file on disk indefinitely. The cleanup is a one-line best-effort unlink; scoping it to resume paths leaves predictable cruft and makes the retirement incomplete. (Already seeded as tracker side-task s16t16; reconfirmed present in the current diff.)

## Suggested fix

Also reap the artifact on every merge invocation: call _cleanup_legacy_merge_state() once at the top of the shared _run_branch_merge entry (covers _merge_start and _merge_retarget) in addition to _resolve_active_merge — so any `skills merge` run, not just a resume, drops the stale file. Alternatively hoist it to a single boundary that every merge subcommand passes through. If the resume-only scope is intentional, document why in the comment so the gap reads as a decision rather than an omission.
