---
id: s04t0301
slug: unify-config-models-with-loadsave
status: done
---

# Unify config models with .load/.save and re-exports

- Rewrite `_source_registry.py`: make `SourceEntry` pydantic `{path: str}` with `repo_root` property; make `SourceRegistry` pydantic with `.load/.save` classmethods and `get_source`/`register_source`/`unregister_source`.
- Add `.load/.save` to `SourceConfig` (defaults on missing file: name="", skills_dir="skills", branch="").
- Add `.load/.save` to `ProviderRegistry`, `SkillManifest` (with_builtins behavior preserved on registry loader function).
- Add `resolve_branch(cfg, git)` and `default_config_dir()` to config package.
- Re-export everything tests need from `config/__init__.py`.
