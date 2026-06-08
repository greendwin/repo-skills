---
id: s10t0104
slug: slice-4-skill-update-name
status: done
---

# Slice 4 — `skill update [name]`

**Goal:** Rework `skill update` and `skill install` with full git integration — auto-detect commits, validate repo state, pull before sync.

## Decisions

- **Never silently overwrite** — if installed files match repo, add manifest entry; if they differ, abort with conflict error
- **Auto-detect commit via `git log -1 --format=%H -- <skill-path>`** — verified against working tree content; manifest never stores `""`
- **Dirty repo is a hard stop** — if skill path has uncommitted changes, refuse to install/update
- **Must be on main branch** — auto-detected via `git symbolic-ref refs/remotes/origin/HEAD`, fallback to `main`
- **`git pull` before install/update** — `--offline` flag skips the pull; without it, pull failure is a hard stop
- **Both `install` and `update` share repo validation** — same rules (clean, main branch, pull)
- **Remove `--commit` from both commands** — commit is always automatic and verified
- **New `_git.py` module behind a protocol** — fake in CLI tests (pyfakefs), real repos in integration tests
- **Caller controls pull** — command logic decides whether to call pull; pull method itself has no offline param
- **History search is a separate future task** — not part of this work

## Key files
`src/skill_cli/main.py`, `src/skill_cli/manifest.py`, `tests/test_update.py`, `tests/test_install.py`, `tests/helper.py`

## Subtasks

- [x] [s10t010401](s10t010401-git-protocol-and-fake-implementation.md): Git protocol + wire into `install`
- [x] [s10t010402](s10t010402-wire-git-validation-into-install.md): Wire git validation into `install`
- [x] [s10t010403](s10t010403-wire-git-validation-into-update.md): Wire git validation into `update`
- [x] [s10t010404](s10t010404-real-gitrepo-implementation.md): Real `GitRepo` implementation
- [x] ~~s10t010405: Make real tests~~
