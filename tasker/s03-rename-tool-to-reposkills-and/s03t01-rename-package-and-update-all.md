---
id: s03t01
slug: rename-package-and-update-all
status: done
---

# Rename package and update all imports

**Goal:** Rename `src/skill_cli/` → `src/repo_skills/`, update all imports across source and tests, update `pyproject.toml` (name, packages, entry point, mypy config, add author/URLs/license). `uv run tox` passes.

**Decisions:**
- Distribution name → `repo-skills`
- Python package → `repo_skills`
- CLI entry point → `skills`
- pyproject.toml metadata: author `Evgeniy A. Cymbalyuk <cimbaluk@gmail.com>`, project URL `https://github.com/greendwin/repo-skills`, license link

**Key files:** `pyproject.toml`, `src/skill_cli/` → `src/repo_skills/`, all `*.py` under `src/` and `tests/`
