---
id: s01t01
slug: slice-1-project-scaffold
status: done
---

# Slice 1 — Project scaffold

**Goal:** Runnable `skill` CLI with no-op click commands, pyproject.toml, dev tooling configured. `skill --help` works.
**Decisions:** Python 3.10+, uv, click, dev tooling (black, isort, mypy strict, flake8), package `skill_cli` in `src/`, `skill` entry point, public API via `__init__.py`, submodules `_`-prefixed.
**Key files:** `pyproject.toml`, `src/skill_cli/__init__.py`, `src/skill_cli/_main.py`
