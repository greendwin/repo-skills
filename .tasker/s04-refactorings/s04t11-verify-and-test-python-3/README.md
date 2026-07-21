---
id: s04t11
slug: verify-and-test-python-3
status: in-progress
---

# Verify and test Python 3.10 support

## Context

`console.py` carried a TODO to verify and test Python 3.10 support. An in-progress attempt instead **dropped** 3.10 (bumped `requires-python` to `>=3.11`, README, black/mypy targets, CI matrix) and added a broad runtime `conftest.py` shim that scanned `sys.modules` to rebind stale real-fs `Path` objects. Investigation shows the source is fully 3.10-clean (compileall passes, all submodules import, `Self` already shimmed via `typing-extensions`), and the pathlib/pyfakefs pain is actually a **3.13+** test-harness issue unrelated to 3.10. Goal: honor the original task — keep 3.10 supported and enforced in CI — and fix the real root cause (import-time `Path` construction in tests) with a refactor rather than a runtime shim.

## Decisions

- **Restore Python 3.10** — source is provably 3.10-clean, so dropping it bought nothing here. Revert `requires-python` to `>=3.10`, README to `3.10+`, black `target-version` to `py310`, and re-add `"3.10"` to the CI matrix. *Rejected: keep 3.10 dropped — there is no real incompatibility justifying it.*
- **mypy targets oldest supported** — set `python_version = "3.10"` so type-checking is against the floor, not a mid-range version.
- **Refactor away import-time `Path`; delete the conftest shim** — pyfakefs patches `pathlib` at `fs`-fixture setup, so any `Path` built at import (module constants, defaults) binds to the real fs; 3.11/3.12 tolerate mixing with fake paths but 3.13+ breaks on cross-fs `relative_to`/`==`. Fix at source: test-side canonical locations become `str` constants; `Path(...)` is built at point of use (test bodies/fixtures/helper bodies, post-patch). *Rejected: runtime rebind shim (fragile, wide, magical, still constructs global Paths); dropping 3.13+ support.*
- **`None`-sentinel for Path-valued helper defaults** — the 5 helper functions defaulting to import-time Paths become `param: Path | None = None` with `Path(...)` built in the body, keeping public signatures `Path`-typed. *Rejected: `str | Path` union defaults — loosens signatures and mixes str/Path at call sites.*
- **Keep tox.ini `basepython` removal + CI `--python ${{ matrix }}` wiring** — the matrix was previously theater (pinned `basepython = python3.12` ran every row under 3.12). Each matrix entry must run under its own interpreter for the matrix (including restored 3.10) to mean anything.
- **Leave `git_real.py:345` throwaway `Path(".")`** — only *surviving* import-time Paths matter; this one is discarded by a no-op protocol check and never meets the fake fs.
- **ADR-0008 recorded** — "No surviving import-time `Path` in tests" (cross-references ADR-0006 for runtime path handling). Already written to `docs/adr/0008-no-import-time-path-in-tests.md`.

## Open questions

- None outstanding.

## Out of scope

- Runtime cross-platform (Windows/POSIX) path semantics — covered by ADR-0006 / task s16.
- Refactoring the src-side `git_real.py` protocol-check Path (deliberately carved out).

## Subtasks

- [x] [s04t1101](s04t1101-defer-path-valued-defaults-in.md): Defer Path-valued defaults in test helpers
- [x] [s04t1102](s04t1102-flip-path-constants-to-str.md): Flip Path constants to str and delete the runtime shim
- [~] [s04t1103](s04t1103-restore-python-3-10-support.md): **review** Restore Python 3.10 support in config and CI matrix
- [ ] [s04t1104](s04t1104-evaluate-a-loc-locations-fixture.md): Evaluate a `loc`/`Locations` fixture to centralize test Path construction
