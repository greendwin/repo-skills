---
id: s04t0403
slug: update-tests-and-helper-for
status: pending
---

# Update tests and helper for new provider API

## Goal

All test files use the new provider API. Test coverage for versioned config.

## Decisions & constraints

- Tests use `Provider`/`ProviderRegistry` from `config`, not `config.deprecated`.
- `TestProviderRegistry` in `test_config.py` must cover versioned load: missing file → creates with builtins; current version → loads as-is; old version → migrates.
- Helper functions updated to use new types.
- No behavioral changes — tests verify the same behaviors through the new API.

## Key files

- `tests/test_config.py`
- `tests/cli/helper.py`
- `tests/cli/test_provider_add.py`
- `tests/cli/test_provider_list.py`
- `tests/cli/test_provider_remove.py`
- `tests/cli/test_status.py`
- `tests/cli/test_install.py`
- `tests/cli/test_update.py`
- `tests/cli/test_merge.py`
- `tests/cli/test_source_init.py`
- `tests/cli/test_source_remove.py`
- `tests/cli/test_uninstall.py`

## Acceptance criteria

- No test imports provider symbols from `config.deprecated`
- `TestProviderRegistry` tests cover versioned load (missing file, current version, old version migration)
- `tox` passes clean
