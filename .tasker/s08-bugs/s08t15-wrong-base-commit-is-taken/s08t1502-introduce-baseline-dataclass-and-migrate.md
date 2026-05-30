---
id: s08t1502
slug: introduce-baseline-dataclass-and-migrate
status: pending
---

# Introduce Baseline dataclass and migrate all access sites

## Goal

Replace flat `commit`/`files` fields on `InstalledSkill` with `baseline: Baseline | None`. Same behavior, new structure that makes invalid states unrepresentable.

## Decisions & Constraints

- `Baseline` dataclass: `commit: str` + `files: dict[str, str]`, stored as `baseline: Baseline | None` on `InstalledSkill`. Either both present or neither.
- Keep `detached` as a separate flag (reachability checks need git, not always available at manifest load time)
- Add `version: int` to `_SkillManifestConfig`, matching `_provider_registry.py` pattern. Older/missing versions → treated as empty manifest (no migration)
- Baseline hashes always come from the source repo, never the installed copy
- Mergeable skills (line 168 in `_merge.py`) register with `baseline=None` — fixes the TODO
- `register_skill` accepts `baseline: Baseline | None` instead of `commit`/`files` kwargs
- Source rename (`_source.py`) passes `baseline=entry.baseline` through
- `_check_divergence` in `_status.py`: skip divergence label when `baseline` is `None`
- `_resolve_diverged_provider`: when `baseline` is `None`, treat all providers with the skill on disk as diverged
- "Already synced" early-out: skip when `baseline` is `None`
- "Nothing to merge" check in `_finalize`: skip when `baseline` is `None`
- `_reattach_installed_skill`: builds `Baseline` from source skill path + commit (needs source path param added)
- `_update.py`: access `entry.baseline.commit` / `entry.baseline.files` with `None` guards

## Key files

- `src/repo_skills/config/_skill_manifest.py`, `src/repo_skills/config/__init__.py`
- `src/repo_skills/cli/_merge.py`, `_install.py`, `_update.py`, `_source.py`, `_status.py`
- `tests/test_config.py`, `tests/cli/test_merge.py`, `tests/cli/test_status.py`, `tests/cli/test_update.py`, `tests/cli/test_install.py`, `tests/cli/test_source_init.py`

## Acceptance criteria

- No `installed.commit` or `installed.files` access anywhere in the codebase
- `register_skill` accepts `baseline: Baseline | None`
- `Baseline` exported from `src/repo_skills/config/__init__.py`
- Loading a v0/missing-version manifest returns empty manifest
- Round-trip save/load preserves `baseline` correctly (both `None` and populated)
- All `None`-baseline cases handled gracefully
- `tox` green
