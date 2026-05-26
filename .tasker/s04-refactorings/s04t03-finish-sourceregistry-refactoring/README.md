---
id: s04t03
slug: finish-sourceregistry-refactoring
status: done
---

# Finish SourceRegistry refactoring

Complete the in-progress source registry refactoring on branch `ref-source-registry`.

**Background.** Commit `d436ae8` started restructuring `repo_skills/config` into a package with `_source.py`, `_source_registry.py`, `_deprecated.py`, `_utils.py`. The refactor introduced a richer `Source` dataclass (`repo_root + config + skills`) and a `SourceRegistry.get_source()` API. CLI files `_merge.py` and `_source.py` are migrated; `_install.py`, `_update.py`, `_status.py` and most tests are not, so `tox` fails.

**Goal.** Finish migration *without* changing functionality. Tests must reflect the new structural layout; behavior must remain identical.

**Reported deviation (approved by user):** `SourceConfig` fields became required (was: `name=""`, `skills_dir="skills"`, `branch=""` defaults). Kept stricter; `SourceConfig.load(...)` will return defaulted instance when file is missing so tests still pass on missing-config path.

**Subtasks:**
- Finalize `config._source_registry`: unify `SourceEntry` (use pydantic `path`-based model with `.repo_root` property), make `SourceRegistry` pydantic with `.load/.save` classmethods and `get_source`/`register_source`/`unregister_source` methods.
- Re-export deprecated symbols from `config/__init__.py` (`ProviderConfig`, `ProviderRegistry`, `SkillEntry`, `SkillManifest`, `SourceEntry`, file-name constants, `load_/save_provider_registry`, `load_/save_skill_manifest`).
- Add module helpers `resolve_branch(cfg, git)` and `default_config_dir()` for tests.
- Add `.load/.save` classmethods/methods on `SourceConfig`, `ProviderRegistry`, `SkillManifest`.
- Migrate `_install.py`, `_update.py`, `_status.py` to use new API (`Source`, `SourceRegistry.get_source`, `entry.repo_root`, `source.get_branch(git)`, `source.skills`).
- Fix `FakeGitRepo` (rename `path`→`root` to satisfy `GitRepo` protocol) and `install_fake_git` typing.
- Update `tests/cli/helper.py` to use re-exported symbols.
- Update `test_config.py` and broken cli test files to use re-exported symbols / restored `.load/.save` API.
- Run `uv run tox` and fix all remaining issues.

## Subtasks

- [x] [s04t0301](s04t0301-unify-config-models-with-loadsave.md): Unify config models with .load/.save and re-exports
- [x] [s04t0302](s04t0302-migrate-installpy-updatepy-statuspy-to.md): Migrate _install.py, _update.py, _status.py to new API
- [x] [s04t0303](s04t0303-update-testshelper-and-test-files.md): Update tests/helper and test files
