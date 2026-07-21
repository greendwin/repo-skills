---
id: s04t1102
slug: flip-path-constants-to-str
status: done
---

# Flip Path constants to str and delete the runtime shim

## Goal

Eliminate every *surviving* import-time `Path` in the test suite by making the canonical location constants `str` and constructing `Path(...)` at point of use, then delete the `_fake_import_time_paths` conftest shim. `uv run tox` green across 3.11–3.14 **without** the shim.

## Decisions & constraints

- Module-level Path constants become `str`: `helper.py:54-57` (`SOURCE_REPO_ROOT`, `SOURCE_CONFIG_DIR`, `REPO_SKILLS_DIR`, `INSTALL_DIR`) and `:456` (`OTHER_REPO_ROOT`); `test_merge.py:51-52` (`CURSOR_DIR`, `OTHER_REPO_ROOT`); `test_install.py:30` (`OTHER_REPO_ROOT`); `test_update_errors.py:29-30` (`SOURCE_A_ROOT`, `SOURCE_B_ROOT`). Derived constants `MANIFEST_PATH`/`SKILLS_DIR` (`helper.py:58-59`) likewise resolve to `str` (build from the str base at point of use, or store as literal str).
- Wrap `Path(...)` at the ~300 use-sites across the ~14 consuming test files so paths are built inside test/fixture/helper bodies (after pyfakefs patches `pathlib`). The Slice-1 deferred defaults already call `Path(<const>)`, so they work unchanged with the new `str` type.
- Delete the `_fake_import_time_paths` autouse fixture (and its `_is_stale_real_path`/`_restore` helpers) from `tests/conftest.py`; keep the `_no_color` fixture.
- Leave `src/repo_skills/git_real.py:345`'s throwaway `Path(".")` — it's discarded by a no-op protocol check and never meets the fake fs (only *surviving* import-time Paths matter).
- Rule recorded in ADR-0008 (`docs/adr/0008-no-import-time-path-in-tests.md`).

## Edge cases

- 3.13+ is the real test: cross-fs `relative_to`/`==` between a real-fs import-time Path and fake paths breaks there. With the shim gone, the only guard is that no surviving import-time Path exists — verify by running the suite on 3.13/3.14, not just the default interpreter.
- A `str` constant used with the `/` operator (`CONST / name`) no longer works — every such site must become `Path(CONST) / name`. Grep each constant's uses; don't miss operator/`.parent`/`.name` sites.
- mypy strict: sites now passing `str` where `Path` is expected must wrap in `Path(...)`; audit signatures that took the constant directly.
- pyfakefs conventions still hold (no real fs, `FakeFilesystem`-typed `fs` fixture).

## Key files

- `tests/conftest.py` (delete shim)
- `tests/cli/helper.py` (constants 54-59, 456)
- `tests/cli/test_merge.py`, `tests/cli/test_install.py`, `tests/cli/test_update_errors.py` (constants)
- ~14 consuming test files: `tests/cli/conftest.py`, `test_source_init.py`, `test_status.py`, `test_uninstall.py`, `test_update.py`, `test_update_attach.py`, `test_update_detached.py`, `test_update_filter.py`, `test_update_output.py`, `test_update_reattach.py` (use-site wrapping)

## Acceptance criteria

- `tests/conftest.py` no longer contains `_fake_import_time_paths` or the stale-path helpers.
- No module-level `Path(...)` constant or Path-valued default remains in `tests/` (grep clean).
- `uv run tox` green across the matrix; specifically the suite passes on Python 3.13 and 3.14 with no shim.
