---
id: s08t2311
slug: reconsider-collapsing-broken-gt-none
status: in-review
---

# Reconsider collapsing BROKEN-&gt;None in load_source_config; expose ConfigState instead of re-stat via source_config_exists

## Context

Surfaced by /dev-loop refactor triage on s08t2308 (delayed finding). **This task explicitly revisits a deliberate, recorded s08t2308 decision** -- treat the decision as reversible only with intent.

s08t2308 chose to collapse the BROKEN state into the same `None` return that MISSING uses in `load_source_config` (`src/repo_skills/config/_source.py`). `load_versioned_config` already distinguishes BROKEN from MISSING, but `load_source_config` flattens both to `None`. Two CLI callers then need the distinction back and re-derive it by re-stat'ing the file via a new helper `source_config_exists`:
- `source init` (`cli/_source.py`): file-exists-but-None => abort without clobbering (data-safety).
- `source list` (`cli/_source.py`): file-exists-but-None => label `(broken)` vs `(not-inited)`.
- `status` already does it the "right" way -- it threads `loaded_source_names` from the scan and checks membership, never re-stat'ing. So the codebase is inconsistent.

Refactor lens (thermo-nuclear) argument: brokenness has no home, so each layer re-encodes it; `source_config_exists` is a lossy proxy (e.g. a valid-but-newer-version file also "exists"), an identity-layer/re-stat smell.

## Decision needed (supersedes the s08t2308 collapse decision)

Stop collapsing BROKEN->None. Options:
- Option A (smaller blast radius): keep `load_source_config -> SourceConfig | None` for the common path, but add `load_source_state(repo_root) -> LoadedConfig[SourceConfig]` (or return `ConfigState` alongside) for the two callers that need broken-vs-missing; delete `source_config_exists`.
- Option B (cleaner): make `load_source_config` return `LoadedConfig[SourceConfig]`; update call sites to branch on `state is ConfigState.OK`.

Either way the BROKEN state flows out of the loader once instead of being destroyed and re-inferred; init/list/status become consistent.

## Caveats / scope

- Preserve all current behavior + tests: malformed source -> status shows `(broken)` exactly one warning; update warn-and-continue; merge raises `SourceBrokenError`; init does NOT overwrite a broken file; list labels `(broken)` vs `(not-inited)`; migration still works.
- Consider folding in the related `_StatusView.loaded_source_names` side-channel cleanup (carry an explicit broken state / read positively) if Option B lands.
- `uv run tox` green.

## Acceptance criteria

- The BROKEN/MISSING distinction is exposed from the loader, not re-derived by re-stat'ing; `source_config_exists` is removed (or justified).
- init/list/status all reason about broken-vs-missing through one mechanism.
- All s08t2308 acceptance criteria remain green.
- `uv run tox` green.
