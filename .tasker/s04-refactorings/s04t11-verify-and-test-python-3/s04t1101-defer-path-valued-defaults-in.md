---
id: s04t1101
slug: defer-path-valued-defaults-in
status: done
---

# Defer Path-valued defaults in test helpers

## Goal

Remove import-time `Path` construction from test-helper **default values** so no `Path` is built at module import via a default arg. Behavior-preserving; `uv run tox` stays green. Remaining constants stay `Path` and the runtime shim stays in place — this slice lands green on its own.

## Decisions & constraints

- Three plain function defaults (`install_skill` `install_dir: Path = INSTALL_DIR`, `create_source_skill` `root: Path = SKILLS_DIR`, `write_broken_source` `root: Path = Path("/repos/broken-project")`) become `param: Path | None = None`, with `param = Path(<const-or-literal>) if param is None else param` in the body. Public signature stays `Path`-typed for callers.
- `FakeGitRepo.root` (dataclass field) uses `field(default_factory=lambda: Path(SOURCE_REPO_ROOT))` so construction defers to instance-creation time (post-pyfakefs-patch); references the existing `SOURCE_REPO_ROOT` constant rather than re-hardcoding the literal.
- `None`-sentinel chosen over `str | Path` union defaults — keeps signatures clean, no str/Path mixing at call sites.
- **DEVIATION (approved during dev-loop refactor):** `create_repo_skill`'s `root` default was NOT converted to a None-sentinel. A refactor review found `root`'s default + the test-helper constant `REPO_SKILLS_DIR = Path("/repo/skills")` + a coverage test formed a closed dead loop — every one of the ~30+ callers already passes `root=` explicitly. Instead the default was DELETED: `root` is now a required `Path` param (reordered ahead of `description` to satisfy Python arg ordering; safe — no caller passes `description` positionally), the helper-level `REPO_SKILLS_DIR` constant was removed, and no coverage test is owed. This removes one constant Slice 2 would otherwise flip. NOTE: the unrelated production `repo_skills.config.REPO_SKILLS_DIR = ".repo-skills"` is a different same-named constant and was untouched.
- Do NOT touch the remaining module-level constants yet (`INSTALL_DIR`, `SKILLS_DIR`, `SOURCE_REPO_ROOT` stay `Path`); do NOT delete the shim. Those are Slice 2.

## Edge cases

- `Path(INSTALL_DIR)` etc. while the constant is still `Path` is `Path(Path(...))` — valid, no behavior change; this is what lets the two constant-type states (Path now, str later) both work.
- Strict mypy: reassigning the `Path | None` param to `Path` in the body narrows cleanly.
- Callers passing the default positionally: none — verified all relevant call sites use keyword args for deferred params.

## Key files

- `tests/cli/helper.py`

## Acceptance criteria

- No default arg or dataclass field in `tests/` constructs a `Path` at import time.
- Callers relying on the (remaining) defaults behave identically (same resolved paths).
- `uv run tox` green (all envs), shim still present.
