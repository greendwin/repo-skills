---
id: s08t3707
slug: extract-shared-skilldir-overwrite-primitive
status: done
---

# Extract shared skill-dir overwrite primitive for update and install

## Goal

Extract a single private helper, e.g. `_overwrite_skill_dir(src: Path, dst: Path) -> None` that does `dst.parent.mkdir(parents=True, exist_ok=True)`, `if dst.exists(): shutil.rmtree(dst)`, `shutil.copytree(src, dst)`, and use it from both copy sites so the copy-into-provider primitive has a single point of change.

## Context

Surfaced by the refactor (duplication) lens during dev-loop review of s08t3704. Both sites implement the same side-effecting primitive (ensure parent dir, remove any pre-existing dst, copytree):
- `src/repo_skills/cli/_update.py` `_apply_actions` — FRESH (`mkdir` + `copytree`) and UPDATE (`rmtree` + `copytree`) arms.
- `src/repo_skills/cli/_install.py` `_copy_skill` — `if dst.exists(): rmtree` then `mkdir` + `copytree`, behind a `force`/exists guard.

If the copy primitive ever changes (e.g. `copytree(dirs_exist_ok=True)`, mode/symlink handling, or atomic temp-dir-then-rename to avoid half-copied skills on failure), both places must change in lockstep today.

## Approach (suggested, not binding)

- `_apply_actions` calls the helper for both FRESH and UPDATE (collapsing the arms, since the helper is idempotent on existence).
- `_install._copy_skill` calls the helper after its `force`/exists guard.
- Pick a shared home (e.g. a small `cli/_copy.py` or alongside existing filesystem utilities) so both CLI modules import one definition.

## Constraints

- Behavior-preserving: the `force` guard / "already exists" error in `install` and the decided-action policy in `update` stay where they are; only the raw copy primitive is shared. Existing tests pass unchanged.
- `uv run tox` green (all environments).
