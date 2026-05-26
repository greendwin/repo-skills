---
id: s04t05
slug: refactor-skillmanifest-out-of-configdeprecated
status: done
---

# Refactor SkillManifest out of config.deprecated

## Context

The `config.deprecated` module's only remaining symbols are manifest-related: `ManifestSkill`, `SkillManifest`, `SKILL_MANIFEST_FILE`, `load_skill_manifest`, `save_skill_manifest`. These need to be migrated into the `config/` package following the same pattern established by `ProviderRegistry` and `SourceRegistry`, so `config.deprecated` can be deleted entirely.

## Decisions

- **Dataclass pattern for public API** — Public types (`InstalledSkill`, `SkillManifest`) are plain dataclasses. Pydantic stays as a private serialization detail (`_SkillManifestConfig`, `_InstalledSkillDesc`). Keeps the `config/` package consistent. *Rejected: moving Pydantic models as-is (simpler but leaks Pydantic into public API, inconsistent with rest of package).*
- **Rename `ManifestSkill` → `InstalledSkill`** — "ManifestSkill" describes where data lives, not what it represents. `InstalledSkill` describes the domain concept. Keep `SkillManifest` as the container name. *Rejected: keeping `ManifestSkill` (marginal but the rename is worth it for domain clarity).*
- **Registry-style API with methods** — Read-only `Mapping` property for `skills`, mutation via `register_skill()`/`unregister_skill()`. Consistent with `ProviderRegistry`/`SourceRegistry`. *Rejected: mutable dict (no invariant protection, inconsistent with other registries).*
- **Method names: `register_skill` / `unregister_skill`** — Consistent with `register_provider`/`unregister_provider` and `register_source`/`unregister_source`. *Rejected: `install`/`uninstall` (user preferred registry consistency).*
- **No `require` method** — Only two call sites would use it, and they have custom error messages. Keep API minimal.
- **No `SKILL_MANIFEST_FILE` re-export** — Implementation detail. Tests should use `load_skill_manifest()`/`save_skill_manifest()` free functions.

## Open questions

None.

## Out of scope

- Any behavioral changes to how the manifest works (pure structural migration).
- Renaming `SkillManifest` itself.

## Context

Second step of the `config.deprecated` elimination. Refactor `SkillManifest` / `ManifestSkill` and their loaders out of `config.deprecated` into the `config/` package. After this, `deprecated.py` can be deleted entirely.

## Decisions

To be grilled separately. Depends on Provider refactoring being complete first — `ManifestSkill` has tighter coupling with Source (the `source` field, the `files` hashes).

## Out of scope

- Provider refactoring (handled by sibling task)

## Subtasks

- [x] [s04t0501](s04t0501-create-skillmanifestpy-with-new-types.md): Create _skill_manifest.py with new types and load/save
- [x] [s04t0502](s04t0502-migrate-cli-commands-to-new.md): Migrate CLI commands to new manifest API
- [x] [s04t0503](s04t0503-migrate-tests-and-delete-configdeprecated.md): Migrate tests and delete config.deprecated
