---
id: s16t23
slug: refactor-mid-upgrade-deferred-keep
status: pending
---

# Refactor: Mid-upgrade deferred --keep-source merges silently retarget the tracking source

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Mid-upgrade deferred --keep-source merges silently retarget the tracking source"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:47-52 (_cleanup_legacy_merge_state) and :1074 (_finalize keep_source derivation)
- severity: major

Before this change a deferred (--no-commit / conflicted) --keep-source merge created a plain `skill-merge/<p>/<s>` branch AND persisted intent in merge-state.json. This change removes the persistence and derives keep-source purely from the branch prefix. For a user who upgrades with such an in-flight merge, the live branch still carries the old plain prefix, so `_finalize` computes keep_source=False and RETARGETS the manifest tracking source — the exact opposite of the user's --keep-source intent — and writes a new baseline, silently corrupting which source the skill tracks. The cleanup only unlinks merge-state.json; it does not detect or warn about the orphaned old-prefix branch. The code comment admits 'deferred keep-source merges from before the upgrade must be re-run', but nothing enforces or surfaces that to the user (tracked separately as s16t17), so the resume completes silently with the wrong result. Deferred: the finding itself scopes the surfacing/migration handling to tracked task s16t17 and the change explicitly accepted the re-run requirement; acting now would scope-creep into that sibling task, and it affects only an upgrade-mid-merge edge case, not the shipped happy path. (Dups finding #8 'Legacy merge-state.json cleanup fires only on resume ... silently downgraded to a retarget', same locations; kept at major.)

## Suggested fix

On resume, if an active merge branch carries the plain `skill-merge/` prefix while a legacy merge-state.json entry for that branch indicated keep-source, abort with an actionable error telling the user to `skills merge --abort` and re-run with --keep-source (read the stale file's keep_source list before unlinking to detect this case), rather than silently retargeting.
