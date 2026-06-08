---
id: s08t31
slug: add-newerversion-guard-to-provider
status: done
---

# Add newer-version guard to provider registry loader; extract shared versioned-config loader

Follow-up from s08t18.

`src/repo_skills/config/_provider_registry.py` (`load_provider_registry`) reimplements the same config-loading ladder as `load_skill_manifest` (build default path → `load_config` → `ConfigBrokenError` warn-and-fallback → `cfg is None` fallback → version comparison), and the two have drifted:

- The provider registry has **no `version > CURRENT_VERSION` guard at all** — it will silently load a registry written by a newer version of the tool, the exact bug class s08t18 fixed for the skill manifest. A newer-than-supported registry should raise `AppError` with an upgrade hint (mirror the manifest message/hint/props).
- On older versions the provider registry runs `_apply_defaults` + persists, whereas the manifest returns empty — the divergence is hand-maintained per loader.

Fix:
1. Extract a shared loader primitive (e.g. `load_versioned_config(model, path, current_version)` in `config/_utils.py`) that centralizes: broken-config warning + fallback, missing-config handling, the `version > current` AppError (newer-version guard), and the `version < current` "discard/migrate" signal. Each loader then only maps its validated `cfg` into its domain object.
2. Route both `load_skill_manifest` and `load_provider_registry` through it, closing the latent provider-registry newer-version hole.

Preserve each loader's existing older-version behavior (manifest: empty; provider registry: apply defaults + persist) unless that behavior is itself decided to be wrong.

Add behavior-level tests: provider registry with `version > CURRENT_VERSION` raises `AppError`; existing provider-registry load/migrate behavior stays green. Follow repo test conventions (pyfakefs, no tmp_path, no inline imports, public-API imports, monkeypatch on module objects).
