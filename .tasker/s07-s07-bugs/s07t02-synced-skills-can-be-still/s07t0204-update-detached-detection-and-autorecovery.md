---
id: s07t0204
slug: update-detached-detection-and-autorecovery
status: done
---

# Update detached detection and auto-recovery

## Goal

Add `detached: bool = False` to `SkillEntry`. During `skills update`, check each installed skill's commit reachability against the pinned branch. Mark as detached if unreachable. Clear detached flag if a previously detached skill's commit is reachable again. Only report state changes.

## Decisions & Constraints

- **`detached` field on SkillEntry, not removal from manifest.** Preserves commit hash and baseline hashes so tracking can auto-recover. *Rejected: removing the entry (loses history, requires `install --force`).*
- **Inline check per skill during update.** Uses `is_ancestor(commit, pinned_branch)`. No separate pass.
- **Skips skills with `commit=None`.** Nothing to check.
- **Only report state changes.** Print when a skill becomes detached or recovers. Silent if unchanged.
- **Installed files are never touched.** Only the manifest flag changes.
- See ADR-0002 for full rationale.

## Key files

- `src/repo_skills/config.py` — add `detached` field to `SkillEntry`
- `src/repo_skills/cli/_update.py` — reachability check + flag management
- `tests/cli/test_update.py` — tests

## Acceptance criteria

- Skill with unreachable commit gets `detached=True` with informational message
- Previously detached skill whose commit is now reachable gets `detached=False` with recovery message
- No message when detached state is unchanged between updates
- Skills with `commit=None` are skipped
