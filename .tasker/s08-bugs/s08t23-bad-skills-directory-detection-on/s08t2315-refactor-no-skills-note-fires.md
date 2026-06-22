---
id: s08t2315
slug: refactor-no-skills-note-fires
status: done
---

# Refactor: "no skills" note fires on a no-op reinit with an unchanged, populated-but-empty dir

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding ""no skills" note fires on a no-op reinit with an unchanged, populated-but-empty dir"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_source.py:110-111,137-138 (_init_or_config_source / _normalize_skills_dirs)
- severity: minor

_normalize_skills_dirs runs unconditionally whenever --skills-dir is supplied, before the fresh-vs-reinit branch. On a reinit where the user re-passes the already-configured dir (e.g. `--skills-dir skills` with an empty skills/ holding only .gitkeep), it still prints `Note: skills currently has no skills.` even though the command reports `already initialized` (no change). The combination ("already initialized" + "has no skills") is contradictory noise for an unchanged dir. test_reinit_with_same_skills_dir_emits_no_change exercises exactly this path and does not assert the note's absence, so the noise is unguarded. The spec calls the soft note 'acceptable', so this is polish, not a violation. The suggested fix restructures where _dir_has_skills runs (moving the note emission into the fresh-init and reinit changed-branch points), changing control flow rather than a local collapse, so it is seeded as delayed.

## Suggested fix

Emit the empty-dir note only when the dir is actually newly set, e.g. defer the _dir_has_skills check to the points where skills_dirs are stored (fresh init and the reinit changed-branch), or suppress it when requested.skills_dirs equals the stored config. Add an assertion to test_reinit_with_same_skills_dir_emits_no_change that 'no skills' is absent.
