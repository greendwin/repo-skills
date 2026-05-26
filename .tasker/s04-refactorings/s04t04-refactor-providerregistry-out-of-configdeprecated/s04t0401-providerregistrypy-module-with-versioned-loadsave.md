---
id: s04t0401
slug: providerregistrypy-module-with-versioned-loadsave
status: done
---

# _provider_registry.py module with versioned load/save

## Goal

New `Provider` dataclass and `ProviderRegistry` class exist with `load`/`save` that handle versioning and builtin injection on first creation.

## Decisions & constraints

- **Versioned config** — `_ProviderRegistryConfig` Pydantic model with `version: int` field. Version 1 injects Claude as default provider. Missing file or old version → create/migrate with builtins, save immediately. Current version → load as-is, no re-injection. Builtins are a one-time default, not a runtime invariant.
- **`Provider` dataclass** — `name: str`, `install_path: Path` (resolved at load time via `expanduser()`). Raw string only lives in the Pydantic serialization model. *Rejected: keep raw string and resolve on demand (redundant work, dishonest type).*
- **Single file `config/_provider_registry.py`** — Provider is simple enough that splitting domain type and registry isn't warranted. *Rejected: two-file split.*
- **Explicit `register_provider`/`unregister_provider`/`require` methods** — encapsulates storage, matches `SourceRegistry` API. Private `_entries` dict, `providers` read-only property.
- **Re-exports from `config/__init__.py`**: `Provider`, `ProviderRegistry`, `load_provider_registry`, `save_provider_registry`.
- **No builtin removal protection** — user can remove "claude" freely. It stays deleted until the next version bump.

## Key files

- `src/repo_skills/config/_provider_registry.py` (new)
- `src/repo_skills/config/__init__.py` (add re-exports)

## Acceptance criteria

- `load_provider_registry()` on missing file creates config with Claude provider at version 1 and persists it
- `load_provider_registry()` on existing version-1 file loads as-is, no re-injection
- `Provider.install_path` is a resolved `Path` (expanduser applied)
- `ProviderRegistry.require()` raises `AppError` for unknown name
- `register_provider`/`unregister_provider` work correctly
- Round-trip save/load preserves all providers
