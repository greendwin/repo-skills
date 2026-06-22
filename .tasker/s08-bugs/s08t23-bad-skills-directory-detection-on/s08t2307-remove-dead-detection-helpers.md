---
id: s08t2307
slug: remove-dead-detection-helpers
status: in-review
---

# Remove dead detection helpers

## Goal

Delete the unused detection helpers that hardcode `root / "skills"` and contradict the new multi-dir model, keeping `tox` green.

## Decisions & constraints

- **Remove dead code** — Delete `resolve_repo_dir` (`cli/_deps.py`) and `find_repo_skills_dir` (`discovery.py`), plus `find_repo_skills_dir`'s tests. Both hardcode `root / "skills"`. `resolve_repo_dir` has no callers (no command `Depends` on it — verified via grep), and `find_repo_skills_dir` is used only by that dead function. Leaving them is a future trap that re-introduces the single-`skills` assumption this task removes. *Rejected: leaving them untouched — they directly contradict the multi-dir model.*
- Remove the now-unused `find_repo_skills_dir` import from `cli/_deps.py`. Keep `find_git_root` and `find_install_dir` (still used).
- Verify before deleting: re-grep for `resolve_repo_dir` / `find_repo_skills_dir` to confirm no live usage crept in via earlier slices.

## Edge cases

- `Manifest.repo_path` / `default_manifest_path` references in the deleted function — ensure no other code relied on the import side effects (it doesn't; the function is self-contained).
- Lint (ruff) must not flag a now-unused import after removal.

## Key files

- `src/repo_skills/cli/_deps.py` — remove `resolve_repo_dir` and its `find_repo_skills_dir` import.
- `src/repo_skills/discovery.py` — remove `find_repo_skills_dir`.
- `tests/test_discovery.py` — remove the four `find_repo_skills_dir` tests (`*_from_git_root`, `*_from_subdirectory`, `*_returns_none_outside_repo`, `*_falls_back_to_manifest`); keep `detect_skills_dir` coverage.

## Acceptance criteria

- `resolve_repo_dir` and `find_repo_skills_dir` no longer exist; grep finds no references.
- No unused imports remain.
- `uv run tox` green (ruff, mypy, pytest all pass).
