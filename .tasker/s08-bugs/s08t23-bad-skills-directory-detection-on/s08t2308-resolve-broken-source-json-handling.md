---
id: s08t2308
slug: resolve-broken-source-json-handling
status: pending
---

# Resolve broken source.json handling (duplicate message / fatal-vs-graceful)

## Context

The s08t2301 slice routed `load_source_config` through `load_versioned_config`. On a malformed `source.json`, `load_versioned_config` prints `Warning: broken config file: <path>` and returns `ConfigState.BROKEN`; `load_source_config` then re-raises `ConfigBrokenError(path)`, which the error handler renders again. Result: the same broken file is reported twice with two different wordings.

Re-raising was chosen to preserve the pre-slice contract (malformed source.json raised `ConfigBrokenError`). But the two sibling versioned loaders (`config/_provider_registry.py`, `config/_skill_manifest.py`) treat BROKEN as "degrade gracefully" (defaults / empty), and the source CLI flows already expect broken sources to warn-and-continue (`tests/cli/test_update_attach.py` TestUpdateBrokenSource, `tests/cli/test_status.py` broken-source tests) for the *missing-config* case.

## Decision needed

Should a malformed `source.json` be fatal or graceful? The clean fix is to collapse BROKEN into the same `None` return that MISSING uses:

    if result.state in (ConfigState.MISSING, ConfigState.BROKEN):
        return None

`load_source` already turns `None` into `SourceBrokenError`, the warning is already printed by the helper, and the duplicate disappears. This aligns source handling with the sibling loaders and the "never crash, warn-and-continue" spirit of the parent story.

## Caveats / scope

- This is a **behavior change** for malformed source.json: today it raises `ConfigBrokenError` (and in `status` is not caught by the `except SourceBrokenError`, so it propagates to a hard error); after the change it would become a `(broken)` warn-and-continue in `status`/`update`/`merge`. Audit those call paths.
- Update `tests/test_config.py::TestSourceConfig` malformed test (currently asserts `ConfigBrokenError`) to the chosen contract (`None` / `SourceBrokenError` + warning emitted).
- Drop the now-unused `ConfigBrokenError` import from `_source.py` if collapsing.

## Acceptance criteria

- A malformed `source.json` produces exactly one user-facing report (no duplicate warning + error).
- `status`/`update`/`merge` behavior on a malformed source is deliberate and tested.
- `uv run tox` green.

Surfaced by /dev-loop refactor triage on s08t2301 (delayed finding).
