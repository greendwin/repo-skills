---
id: s04t0503
slug: migrate-tests-and-delete-configdeprecated
status: pending
---

# Migrate tests and delete config.deprecated

## Goal

All test files use new manifest API. `config/deprecated.py` is deleted. No references to `config.deprecated` remain anywhere.

## Decisions & constraints

- **`save_manifest`/`load_manifest` helpers** in `helper.py` switch to `save_skill_manifest`/`load_skill_manifest` free functions from `config`.
- **`SKILL_MANIFEST_FILE` references removed** — tests that construct paths manually should use the free functions instead.
- **`test_config.py` `TestSkillManifest`** rewritten against new types (`InstalledSkill`, `SkillManifest` dataclasses, `register_skill`/`unregister_skill`).
- **All test files** replace `ManifestSkill` with `InstalledSkill` and import from `repo_skills.config`.
- **Delete `src/repo_skills/config/deprecated.py`** — nothing should remain.

## Key files

- `tests/cli/helper.py`
- `tests/test_config.py`
- `tests/cli/test_install.py`, `test_merge.py`, `test_status.py`, `test_update.py`, `test_uninstall.py`, `test_source_init.py`, `test_source_remove.py`
- `src/repo_skills/config/deprecated.py` (deleted)

## Acceptance criteria

- `config/deprecated.py` no longer exists
- All tests pass
- `grep -r "config.deprecated"` returns nothing
