---
id: s08t39
slug: relax-clean-repo-guard-in
status: pending
---

# Relax clean-repo guard in ensure_on_branch for the no-checkout path

## Context

`ensure_on_branch` refuses to proceed when the *whole* source repo is dirty, even when no branch switch or pull is needed. Unrelated WIP elsewhere in the repo then blocks `install`/`merge`/`update`. Goal: scope the clean-check to the skill path(s) actually being operated on, so unrelated changes don't block — while keeping the whole-repo guard wherever a checkout or pull touches the whole working tree.

## Decisions

- **Replace `require_clean: bool` with `clean_paths: list[str] | None`** — the boolean carried no information `clean_paths` can't. New signature: `ensure_on_branch(git, branch, *, pull=False, clean_paths=None)`. Rules: if a checkout or pull is needed → whole-repo clean required (`clean_paths` ignored, since checkout/pull touch the whole tree); elif `clean_paths is not None` → require those paths clean; else → no check. Empty list degenerates to "no check" — no sentinel needed. *Rejected: keeping `require_clean` and adding `clean_paths` alongside — every real caller is expressible by `clean_paths` alone, so the boolean is redundant.*
- **Scope the merge commit, not just the clean-check** — `_merge_start`/`_merge_orphan` call `git.commit_all` = `git add -A && git commit`, and `create_branch` (`checkout -b <base>`) carries uncommitted WIP onto the merge branch. So merely relaxing the guard would let `commit_all` sweep unrelated WIP into the skill-merge commit and back onto the pinned branch (corruption). The commit must be scoped to the skill path: `git add -A -- <skill.rel_path>` (the `-A -- <path>` form so deletions from `overwrite_dir` are staged), then commit. Orphan-merge scopes to `active_dir/<skill_name>`. This is also simply *more correct* — a merge commit should never contain unrelated files. *Rejected: install-only relaxation (leaves the "WIP blocks merge" complaint half-fixed and reintroduces a whole-repo mode); stashing unrelated changes (fragile, surprising).*
- **Per-caller `clean_paths` mapping** — `merge` → `[skill.rel_path]`; `install`/orphan-merge → thread the skill path through `prepare_source_repo`; `update` → `source.skills_dirs` (config-level, available from `get_source_no_skills` with no tree scan — avoids the chicken-and-egg of resolving per-skill `rel_path`s before the branch is known); `status` → `None` (was `require_clean=False`). *Rejected for update: per-skill scoping (forces `_sync_source_repos` to scan on a possibly-wrong branch, defeating its design); no scoping (relaxes update's guard and reintroduces the dirty-source-read hazard where copied files don't match the recorded baseline commit).*

## Edge cases

- `update` reads source content into installs; a dirty *other* skill in the same `skills_dir` still blocks (acceptable — that dir isn't clean). Unrelated WIP outside `skills_dirs` no longer blocks.
- `clean_paths` is only ever consulted on the no-checkout/no-pull path (already on the pinned branch), so scoped scanning is always safe there.
- If unrelated dirty files differ between HEAD and the merge base commit, `checkout -b <base>` may fail with a git error — the merge aborts safely with no corruption. Accepted; not engineered around this round.

## Key files

- `src/repo_skills/git.py` — `ensure_on_branch` (signature + scoping logic); remove the existing `TODO`.
- `src/repo_skills/git_real.py` — `is_clean` (needs a path-scoped variant, e.g. `git status --porcelain -- <paths>`); `commit_all` callers.
- `src/repo_skills/cli/_merge.py` — `_merge_start`, `_merge_orphan` (pass `clean_paths`; scope the commit to the skill path).
- `src/repo_skills/cli/_deps.py` — `prepare_source_repo` (accept + forward skill path(s)).
- `src/repo_skills/cli/_install.py` — pass the skill path to `prepare_source_repo`.
- `src/repo_skills/cli/_update.py` — `_sync_source_repos` (pass `source.skills_dirs`).
- `src/repo_skills/cli/_status.py` — `clean_paths=None`.

## Acceptance criteria

- `ensure_on_branch` with `clean_paths=[path]`, already on branch, no pull: a repo dirty *only outside* `path` proceeds; a repo dirty *inside* `path` raises.
- `ensure_on_branch` with a needed checkout or pull: any dirty repo raises regardless of `clean_paths`.
- `merge --offline` of a skill with unrelated WIP elsewhere in the source: succeeds, and the resulting merge commit contains **only** the skill's files (no unrelated WIP).
- `install --offline` with unrelated WIP in the source repo: succeeds.
- `update --offline` with WIP outside `skills_dirs`: succeeds; with WIP inside a `skills_dir`: blocks.
- The `TODO` in `ensure_on_branch` is removed.

## Open questions

- None.

## Out of scope

- Stash/auto-resolve of unrelated dirty files that conflict with `checkout -b` at the base commit (left as a safe-abort edge).
