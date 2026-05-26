---
id: s04t0502
slug: migrate-cli-commands-to-new
status: pending
---

# Migrate CLI commands to new manifest API

## Goal

All 5 CLI modules import manifest symbols from `repo_skills.config` instead of `config.deprecated`. No behavioral changes.

## Decisions & constraints

- **`ManifestSkill` → `InstalledSkill`** at all call sites.
- **Dict mutation → methods**: `manifest.skills[name] = InstalledSkill(...)` → `manifest.register_skill(name, ...)`. `manifest.skills.pop(name)` → `manifest.unregister_skill(name)`.
- **Read access unchanged**: `manifest.skills.get()`, `name in manifest.skills`, iteration all work via read-only `Mapping` property.
- **Direct field mutation in `_merge.py` `_finalize`**: `entry.commit = ...` and `entry.files = ...` need attention — either re-register the skill or the dataclass fields are mutable. Since `InstalledSkill` is a dataclass (not frozen), direct field mutation is fine, but re-registering is cleaner and consistent with the registry pattern.
- **No behavioral changes** — pure structural migration.

## Key files

- `src/repo_skills/cli/_install.py`
- `src/repo_skills/cli/_update.py`
- `src/repo_skills/cli/_status.py`
- `src/repo_skills/cli/_merge.py`
- `src/repo_skills/cli/_source.py`

## Acceptance criteria

- No imports from `config.deprecated` in any CLI module
- All existing CLI tests still pass unchanged
