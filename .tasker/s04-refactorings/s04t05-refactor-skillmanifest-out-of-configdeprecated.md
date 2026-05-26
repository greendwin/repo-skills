---
id: s04t05
slug: refactor-skillmanifest-out-of-configdeprecated
status: pending
---

# Refactor SkillManifest out of config.deprecated

## Context

Second step of the `config.deprecated` elimination. Refactor `SkillManifest` / `ManifestSkill` and their loaders out of `config.deprecated` into the `config/` package. After this, `deprecated.py` can be deleted entirely.

## Decisions

To be grilled separately. Depends on Provider refactoring being complete first — `ManifestSkill` has tighter coupling with Source (the `source` field, the `files` hashes).

## Out of scope

- Provider refactoring (handled by sibling task)
