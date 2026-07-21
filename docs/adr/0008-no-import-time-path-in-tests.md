# No surviving import-time `Path` in tests

## Context

The test suite runs against **pyfakefs**, which patches `pathlib` at `fs`-fixture
setup — *after* test modules are imported. Any `Path` object built at import time
(module-level constants, dataclass field defaults, function default args) is
therefore bound to the **real** filesystem's path classes, not the fake ones.

Mixing such a stale real-fs `Path` with fake-fs paths inside a test is tolerated
on 3.11/3.12 but **breaks on 3.13+** (the rewritten `pathlib`): cross-fs
`relative_to`/`==` no longer interoperate across the real and pyfakefs class
hierarchies. This surfaced as obscure comparison failures only on the 3.13+ CI
matrix rows.

An earlier fix rebound stale paths at runtime via an autouse `conftest` fixture
that scanned `sys.modules` and patched `__defaults__`/`__kwdefaults__`. It worked
but was wide-reaching, magical, and easy to break.

## Decision

Tests must not let an import-time `Path` **survive** to be used against the fake
fs. Concretely:

- Test-side canonical locations (`INSTALL_DIR`, `SOURCE_REPO_ROOT`, …) are `str`
  constants, not `Path`. Callers build `Path(...)` at point of use — inside test
  bodies, fixtures, or helper functions, all of which run after pyfakefs patches
  `pathlib`.
- Helper functions default their `Path` params via a `None` sentinel
  (`root: Path | None = None`; build `Path(...)` in the body), keeping the public
  signature `Path`-typed while deferring construction past the patch boundary.
- No runtime rebind shim.

**Carve-out:** only *surviving* import-time Paths matter. A `Path` built at import
and immediately discarded without ever meeting the fake fs (e.g. the throwaway
`RealGitRepo(Path("."))` protocol check in `git_real.py`) is fine.

Related runtime path-handling rules live in [ADR-0006](0006-cross-platform-path-handling.md).

## Considered Options

- **Runtime rebind shim** (autouse fixture scanning `sys.modules`, patching
  function `__defaults__`). Rejected: fragile, broad, and magical — it still
  constructs Paths in global scope and papers over the root cause.
- **Drop Python 3.13+ support.** Rejected: the harness must track supported
  runtimes, not the reverse.
- **`str`/`Path` union defaults** instead of a `None` sentinel. Rejected: loosens
  helper signatures and mixes `str`/`Path` at call sites.
