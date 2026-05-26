---
id: s04t0402
slug: migrate-cli-commands-to-new
status: pending
---

# Migrate CLI commands to new provider API

## Goal

All production CLI files import from `config` instead of `config.deprecated` for provider symbols. No behavioral changes.

## Decisions & constraints

- **`Provider.install_path`** replaces `pcfg.resolve_path()` and `pcfg.resolve_path(skill_name)` → `provider.install_path / skill_name`.
- **`deprecated.py` keeps only Manifest symbols** — `ProviderConfig`, `ProviderRegistry`, `BUILTIN_PROVIDER_NAME`, `BUILTIN_PROVIDER_INSTALL_DIR`, `load_provider_registry`, `save_provider_registry` are removed from it.
- **No behavioral changes** — pure structural refactoring.
- **`_provider.py` CLI** — currently loads twice (with/without builtins). New API eliminates this: builtins are injected on first creation only, so a single `load_provider_registry()` is always sufficient. `register_provider`/`unregister_provider` replace direct dict mutation.

## Key files

- `src/repo_skills/cli/_provider.py`
- `src/repo_skills/cli/_install.py`
- `src/repo_skills/cli/_update.py`
- `src/repo_skills/cli/_status.py`
- `src/repo_skills/cli/_merge.py`

## Acceptance criteria

- No production code imports provider symbols from `config.deprecated`
- `deprecated.py` no longer contains `ProviderConfig`, `ProviderRegistry`, or their loaders
- All existing CLI behavior preserved
- `tox` passes
