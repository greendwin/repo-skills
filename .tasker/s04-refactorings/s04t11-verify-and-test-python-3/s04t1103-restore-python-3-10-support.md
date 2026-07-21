---
id: s04t1103
slug: restore-python-3-10-support
status: in-review
---

# Restore Python 3.10 support in config and CI matrix

## Goal

Restore Python 3.10 as a supported, CI-enforced runtime — delivering the original task's "verify and test 3.10 support" intent — on top of the shim-free base from the earlier slices. `uv run tox` green; 3.10 runs as a real matrix row.

## Decisions & constraints

- Revert the 3.10-drop across config surfaces: `pyproject.toml` `requires-python` → `>=3.10`; `README.md` Requirements → `Python 3.10+`; `[tool.black]` `target-version` → `["py310"]`; `[tool.mypy]` `python_version` → `"3.10"` (type-check against the supported floor).
- Re-add `"3.10"` to the `.github/workflows/ci.yml` matrix (`["3.10", "3.11", "3.12", "3.13", "3.14"]`).
- KEEP the already-made `tox.ini` `basepython` removal and the CI `uv run --python ${{ matrix.python-version }} tox` wiring — without these the matrix was theater (every row ran under the pinned 3.12). Each matrix row must run under its own interpreter.
- Source is already 3.10-clean (`Self` shimmed via `typing-extensions`; no 3.11+ syntax/stdlib) — no source changes expected. The `console.py` TODO is already removed.

## Edge cases

- Confirm `tox-uv` honors `uv run --python 3.10 tox` for all three envs (typecheck/test/lint), i.e. the 3.10 interpreter actually drives each env.
- mypy at `python_version = "3.10"` may surface version-floor type issues masked at 3.11 — fix any that appear (CLAUDE.md: fix all tox issues, incl. pre-existing).
- Ensure no dependency lower-bound silently excludes 3.10 (deps already resolve on 3.10 per investigation).

## Key files

- `pyproject.toml` (`requires-python`, `[tool.black]`, `[tool.mypy]`)
- `README.md` (Requirements section)
- `.github/workflows/ci.yml` (matrix)
- `tox.ini` (keep `basepython` removed)

## Acceptance criteria

- `pyproject.toml` declares `requires-python = ">=3.10"`; README states `Python 3.10+`; black targets `py310`; mypy `python_version = "3.10"`.
- CI matrix includes `"3.10"` and each row runs under its own interpreter via `uv run --python`.
- `uv run tox` green (all envs) locally; the package imports and the suite passes on Python 3.10.
