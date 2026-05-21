---
id: s02t12
slug: pinned-branch-in-source-init
status: pending
---

# Pinned branch in `source init` + remove `--any-branch`

**Goal:** `source init` captures the current branch as the "pinned branch" in `source.json`. All write operations (`merge`, `install`, `update`) target the pinned branch instead of assuming `main`. Remove `--any-branch` flag — user changes the pin via `source init --branch`.

## Decisions

- **`branch: str = ""` on `SourceConfig`** — empty default means existing `source.json` files work without migration; lazy-resolves to `get_main_branch()`.
- **Free function `resolve_branch(config, git)`** — lives near `SourceConfig` in `config.py`; single place for fallback logic, not a method on the dataclass.
- **`source init` writes current branch explicitly** — first init captures `git.current_branch()` into the `branch` field.
- **`init --branch <name>` for changing the pin** — no new subcommand; reuses idempotent reinit. Validates branch exists locally.
- **Reinit preserves existing pin** — unless `--branch` is explicitly passed, the stored `branch` value is untouched.
- **Remove `--any-branch` from `install` and `update`** — no deprecation; young CLI with no external consumers.
- **`_validate_repo(git, branch: str)` signature** — caller passes resolved branch string; function stays minimal.
- **Install/update validate-only, no auto-checkout** — error message references pinned branch and includes copy-pasteable hint: `source init --branch <current>`.
- **Merge replaces `get_main_branch()` with `resolve_branch()`** — all three sites (`_merge_start`, `_merge_continue`, `_merge_abort`).

**Key files:** `src/repo_skills/config.py`, `src/repo_skills/cli/_source.py`, `src/repo_skills/cli/_install.py`, `src/repo_skills/cli/_update.py`, `src/repo_skills/cli/_merge.py`, tests

## Subtasks

- [x] [s02t1201](s02t1201-resolvebranch-function-sourceconfigbranch-field.md): `resolve_branch` function + `SourceConfig.branch` field
- [x] [s02t1202](s02t1202-source-init-writes-current-branch.md): `source init` writes current branch + `--branch` flag
- [ ] [s02t1203](s02t1203-remove-anybranch-wire-validaterepo-to.md): Remove `--any-branch`, wire `_validate_repo` to pinned branch
- [ ] [s02t1204](s02t1204-merge-targets-pinned-branch.md): Merge targets pinned branch
