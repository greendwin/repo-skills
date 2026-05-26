---
id: s04t0302
slug: migrate-installpy-updatepy-statuspy-to
status: done
---

# Migrate _install.py, _update.py, _status.py to new API

- `_install.py`: use `SourceRegistry.get_source(name, load_skills=False/True)`, `Source.repo_root/config/get_branch(git)/skills`. Pull deprecated symbols from re-exports.
- `_update.py`: same pattern; drop `resolve_branch` arg flow in favor of `source.get_branch(git)`.
- `_status.py`: replace `list_source_skills(path)` with `load_source(path, load_skills=True).skills`; replace `sentry.path` with `sentry.repo_root`.
