---
id: s04t0501
slug: create-skillmanifestpy-with-new-types
status: done
---

# Create _skill_manifest.py with new types and load/save

## Goal

`InstalledSkill`, `SkillManifest`, `load_skill_manifest`, `save_skill_manifest` exist in `config/` with dataclass public API, Pydantic serialization hidden, and are re-exported from `config/__init__.py`.

## Decisions & constraints

- **Dataclass pattern** — Public types (`InstalledSkill`, `SkillManifest`) are plain dataclasses. Private `_InstalledSkillDesc` / `_SkillManifestConfig` handle Pydantic serialization. Same pattern as `_provider_registry.py` and `_source_registry.py`. *Rejected: moving Pydantic models as-is (leaks Pydantic into public API).*
- **Rename `ManifestSkill` → `InstalledSkill`** — "ManifestSkill" describes storage, not domain. `InstalledSkill` describes what it represents. *Rejected: keeping `ManifestSkill` (domain clarity wins).*
- **Registry-style API** — `SkillManifest` has read-only `skills: Mapping[str, InstalledSkill]` property, mutation via `register_skill(name, ...)` / `unregister_skill(name)`. Consistent with `ProviderRegistry`/`SourceRegistry`. *Rejected: mutable dict (inconsistent, no invariant protection).*
- **No `require` method** — only two call sites would use it with custom error messages. Keep API minimal.
- **No `SKILL_MANIFEST_FILE` re-export** — implementation detail, tests use free functions.
- **Backward-compatible JSON** — same file name (`skill-manifest.json`), same keys. Rename is code-only.

## Edge cases

- Missing manifest file → returns empty `SkillManifest`
- Empty manifest file → returns empty `SkillManifest`

## Key files

- `src/repo_skills/config/_skill_manifest.py` (new)
- `src/repo_skills/config/__init__.py` (add re-exports)
- `tests/test_config.py` (new tests for the module)

## Acceptance criteria

- `load_skill_manifest()` returns `SkillManifest` with `InstalledSkill` entries
- Round-trip save/load preserves all data (source, commit, files)
- Missing file returns empty manifest
- `register_skill`/`unregister_skill` mutate state correctly
- `skills` property is read-only `Mapping`
