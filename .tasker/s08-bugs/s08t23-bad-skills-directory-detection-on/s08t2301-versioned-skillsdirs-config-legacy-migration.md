---
id: s08t2301
slug: versioned-skillsdirs-config-legacy-migration
status: done
---

# Versioned skills_dirs config + legacy migration

## Goal

`SourceConfig` carries a list of skills dirs and is versioned, so a `source.json` with the old single `skills_dir: str` loads as `skills_dirs: list[str]` and round-trips at version 1. Reading a legacy (v0) file migrates it in place. No command behavior changes yet beyond reading/writing the new shape — this is the foundation every later slice consumes.

## Decisions & constraints

- **Multi-dir data model** — `SourceConfig` becomes a `VersionedConfig` with `CURRENT_VERSION = 1` and `skills_dirs: list[str]` replacing `skills_dir: str`. *Rejected: a `str | list[str]` union (leaves a union type to handle everywhere); a separate `extra_dirs: list[str]` field (muddies scan/merge semantics — there is one ordered list, first entry is the active dir).*
- **Legacy migration on load** — A v0 file looks like `{"name": ..., "skills_dir": "skills", "branch": ...}` (no `version` key → pydantic default `version=0`). Load via the `load_versioned_config` machinery (`config/_utils.py`). When state is `OUTDATED` (v0), convert `skills_dir` → `skills_dirs=[skills_dir]`, **carry name/branch forward** (do NOT discard like the manifest/provider-registry do), clear the legacy field, bump to version 1, and re-save the file. *Rejected: discarding old data on OUTDATED (loses name/branch); a pure pydantic alias/validator with no version bump (the project standard is the versioning mechanism, and re-saving normalizes the file once so the legacy key disappears).*
- **Re-save on read is acceptable** — `load_source_config` is called from read-only commands (`status`, `merge`); a load-time re-save means those rewrite `source.json`. `config/_provider_registry.py` already re-saves on read, so this is consistent with the codebase.
- The model must still *parse* the legacy `skills_dir` key at migration time (e.g. keep a `skills_dir: str | None = None` field used only during migration), but must not serialize it once migrated.

## Edge cases

- A v0 file with `skills_dir` absent or empty — produce `skills_dirs=[]` (later slices guarantee non-empty on write; loaders must tolerate `[]`).
- A file already at version 1 loads with no migration and no re-save.
- A file with `version` greater than 1 — existing machinery raises "Config was written by a newer version of the tool" (unchanged behavior; keep it working).
- Don't serialize `skills_dir: null` after migration.

## Key files

- `src/repo_skills/config/_source.py` — `SourceConfig`, `load_source_config`, `save_source_config`, `load_source`, `_collect_source_skills` signature.
- `src/repo_skills/config/_utils.py` — `VersionedConfig`, `load_versioned_config`, `ConfigState`.
- `src/repo_skills/config/_skill_manifest.py`, `_provider_registry.py` — reference patterns for versioned load + migrate + re-save.
- Tests: `tests/test_config.py` (existing `SourceConfig(..., skills_dir="skills")` usages will need updating to `skills_dirs`), and all `SourceConfig(...)` constructions in `tests/cli/helper.py`, `tests/cli/test_merge.py`, `tests/cli/test_status.py`, `tests/cli/test_install.py`, `tests/cli/test_update_attach.py`, `tests/cli/test_source_init.py`.

## Acceptance criteria

- Saving a `SourceConfig(name=..., skills_dirs=["a", "b"], branch=...)` writes `version: 1` and a `skills_dirs` array; loading it back yields the same list.
- Loading a legacy file `{"name": "x", "skills_dir": "skills", "branch": "main"}` returns `skills_dirs == ["skills"]`, preserves name and branch, and re-writes the file at version 1 with no `skills_dir` key.
- Loading a v1 file does not re-save it.
- A config with `version` 2 still raises the newer-version error.
- `uv run tox` is green (all `SourceConfig` test constructions migrated to `skills_dirs`).
