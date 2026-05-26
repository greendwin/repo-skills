---
id: s04t04
slug: refactor-providerregistry-out-of-configdeprecated
status: pending
---

# Refactor ProviderRegistry out of config.deprecated

## Context

Refactor `ProviderRegistry` out of `config.deprecated` into the new `config/` package, following the same pattern established by the `SourceRegistry` refactoring. First of two steps (Provider now, Manifest later). Goal is consistency across the config package and eventual elimination of the deprecated module.

## Decisions

- **Two-step deprecation** — Provider first, Manifest second. Provider has no cross-references to Source, making it a cleaner first target. *Rejected: single pass (too much churn, Manifest coupling complicates it).*
- **Same structural pattern as SourceRegistry** — non-Pydantic class wrapping internal Pydantic config, with free `load`/`save` functions. Keeps the config package consistent.
- **Single file `config/_provider_registry.py`** — Provider is simple enough (name + path) that splitting domain type and registry into two files isn't warranted. *Rejected: `_provider.py` + `_provider_registry.py` split (overkill for this complexity).*
- **`Provider` dataclass with resolved `Path`** — `install_path: Path` resolved at load time via `expanduser()`. Raw string only lives in the Pydantic serialization model. Every consumer calls `resolve_path()` anyway. *Rejected: keep raw string and resolve on demand (redundant work, dishonest type).*
- **Explicit `register_provider`/`unregister_provider` methods** — encapsulates storage, matches `SourceRegistry` API.
- **Versioned config with one-time builtin injection** — `providers.json` gets a `version: int` field. Missing file or old version → create/migrate with Claude provider injected, save immediately. Current version → load as-is. Builtins are a one-time default, not a runtime invariant. *Rejected: always-inject-on-load with save filtering (extra complexity); `with_builtins` parameter (split-brain loading).*
- **No builtin removal protection** — user can freely remove the "claude" provider. Trust the user. *Rejected: guard against removing builtin (paternalistic, breaks if user legitimately doesn't want it).*
- **Re-exports from `config/__init__.py`**: `Provider`, `ProviderRegistry`, `load_provider_registry`, `save_provider_registry`. Internal Pydantic models and constants stay private.
- **`deprecated.py` stays until Manifest refactoring** — renaming mid-way would cause every import to change twice.

## Open questions

None — all Provider-side decisions resolved.

## Out of scope

- `SkillManifest` / `ManifestSkill` refactoring (second step, separate task)
- `SourceRegistry` versioning (no immediate need)
- Any behavioral changes to CLI commands — pure structural refactoring

## Subtasks

- [x] [s04t0401](s04t0401-providerregistrypy-module-with-versioned-loadsave.md): _provider_registry.py module with versioned load/save
- [x] [s04t0402](s04t0402-migrate-cli-commands-to-new.md): Migrate CLI commands to new provider API
- [ ] [s04t0403](s04t0403-update-tests-and-helper-for.md): Update tests and helper for new provider API
