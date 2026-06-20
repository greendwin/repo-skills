---
id: s08t2310
slug: unify-versioned-config-migration-via
status: done
---

# Unify versioned-config migration via a raw-dict / migrate hook on load_versioned_config

## Context

Surfaced by /dev-loop refactor triage on s08t2308 + s08t2309 (delayed finding).

The v0->v1 source migration in `load_source_config` (`src/repo_skills/config/_source.py`) currently:
- reads `source.json` TWICE on the OUTDATED path: once via `load_versioned_config(SourceConfig, ...)` (to detect the version), then again via `load_config(_SourceConfigV0, path)` (to recover the legacy `skills_dir`, since the current `SourceConfig` no longer carries it);
- needs a TOCTOU guard `if legacy is None: return None` purely because of that second read;
- builds the v1 model via a manual per-field allow-list (`SourceConfig(name=..., skills_dirs=..., branch=...)`), so any field added to `SourceConfig` later is silently dropped to its default during migration, with no test catching it.

Meanwhile the three consumers of `load_versioned_config` (`_source.py`, `_provider_registry.py`, `_skill_manifest.py`) each open-code their own non-OK handling; there is no canonical migration seam.

## Decision needed / proposed shape

Have `load_versioned_config` carry forward what migration actually needs (the raw parsed dict it already read), and/or accept an optional `migrate: Callable[[dict], _C]` hook that the loader invokes on OUTDATED and persists. Then the source OUTDATED branch becomes a single pass with no second read, no TOCTOU branch, and no manual field allow-list, and provider/manifest can converge on the same dispatcher.

## Caveats / scope

- `LoadedConfig.cfg` is currently typed as the TARGET model `_C`, which is the wrong shape for migration (it has already coerced into the new model). Adding `raw: dict | None` (or similar) is the root change.
- Shared blast radius: `load_versioned_config` / `LoadedConfig` are used by all 3 loaders -- keep their existing behavior green (provider defaults injection, manifest empty-start, source v0->v1; v1 no-resave; v2 raises; absent/empty -> []).
- Keep all s08t2308 + s08t2309 acceptance criteria green.
- `uv run tox` green.

## Acceptance criteria

- v0->v1 source migration reads `source.json` once (no double read) and no longer needs the `if legacy is None` TOCTOU guard.
- Migration no longer silently drops future `SourceConfig` fields (covered by a test).
- A single migration seam is shared across source/provider/manifest (or a clear, justified reason if one loader stays bespoke).
- `uv run tox` green.
