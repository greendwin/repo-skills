---
id: s04t1101
slug: defer-path-valued-defaults-in
status: pending
---

# Defer Path-valued defaults in test helpers

## Goal

Remove import-time `Path` construction from test-helper **default values** so no `Path` is built at module import via a default arg. Behavior-preserving; `uv run tox` stays green. Constants remain `Path` and the runtime shim stays in place — this slice lands green on its own.

## Decisions & constraints

- The four plain function defaults (`helper.py:328` `root: Path = REPO_SKILLS_DIR`, `:350` `root: Path = Path("/repos/broken-project")`, `:433` `install_dir: Path = INSTALL_DIR`, `:445` `root: Path = SKILLS_DIR`) become `param: Path | None = None`, with `param = Path(<const-or-literal>) if param is None else param` in the body. Public signature stays `Path`-typed for callers.
- `FakeGitRepo.root` (`helper.py:64`) is a **dataclass field**, not a function default — a `None`-sentinel is awkward there. Use `field(default_factory=lambda: Path("/repos/my-project"))` so construction defers to instance-creation time (post-pyfakefs-patch).
- `None`-sentinel chosen over `str | Path` union defaults — keeps signatures clean, no str/Path mixing at call sites.
- Do NOT touch the module-level constants yet (they stay `Path`); do NOT delete the shim. Those are Slice 2.

## Edge cases

- `Path(REPO_SKILLS_DIR)` etc. while the constant is still `Path` is `Path(Path(...))` — valid, no behavior change; this is what lets the two constant-type states (Path now, str later) both work.
- Strict mypy: reassigning the `Path | None` param to `Path` in the body narrows cleanly; confirm no `--strict` complaint.
- Preserve any callers that pass the default positionally — the reconstructed value must equal the old default exactly.

## Key files

- `tests/cli/helper.py` (lines 64, 328, 350, 433, 445)

## Acceptance criteria

- No default arg or dataclass field in `tests/` constructs a `Path` at import time (grep: no `: Path = Path(` / `: Path = <CONST>` remaining in helper signatures).
- Callers relying on the defaults behave identically (same resolved paths).
- `uv run tox` green (all envs), shim still present.
