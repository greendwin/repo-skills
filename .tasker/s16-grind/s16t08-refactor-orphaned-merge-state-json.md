---
id: s16t08
slug: refactor-orphaned-merge-state-json
status: in-review
---

# Refactor: Orphaned merge-state.json left on disk for upgrading users; no cleanup

## Refactor side-task
- depth: 1
- origin: s16t03 — refactor finding "Orphaned merge-state.json left on disk for upgrading users; no cleanup"

## Goal

Apply the deferred refactoring surfaced while processing s16t03.
- location: src/repo_skills/config/_merge_state.py (deleted) / src/repo_skills/cli/_merge.py
- severity: nit

The old mechanism persisted keep-source intent to ~/.config/repo-skills/merge-state.json. Removing the module means nothing ever reads or deletes that file again, so any user who had a deferred keep-source merge under the previous version is left with a stale merge-state.json forever. It is harmless (nothing reads it), but it is dangling cruft from a real on-disk artifact. Routed to delayed because the fix introduces NEW behavior beyond this refactor — best-effort disk unlink and/or an in-flight migration-handling decision (documenting that pre-upgrade deferred keep-source merges must be re-run). That extends scope past the behavior-preserving branch-name refactor and warrants its own seed rather than being forced in place here.

## Suggested fix

File a side-task: on merge --continue/--abort (or a one-time load) best-effort unlink default_config_path("merge-state.json") via path.unlink(missing_ok=True), OR explicitly document that pre-upgrade deferred keep-source merges must be re-run. Decide as a deliberate migration step, not an in-place refactor edit.
