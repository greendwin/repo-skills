---
id: s08t3704
slug: enforce-the-baseline-invariant-in
status: pending
---

# Enforce the baseline invariant in update and install

## Goal

`skills update` never half-applies a copy. `_update_skill` resolves the verified source commit **before** the provider copy loop and only copies when a valid baseline can be constructed. A committed-but-dirty source aborts that one skill with a precise error (files and baseline untouched); a source whose pull failed is skipped with an honest label; and `install`'s commit resolution shares the same precise error. This delivers the observable behavior on top of the `CommitVerification` object from the previous slice, and removes the now-unreachable branch in `_advance_baseline`.

## Decisions & constraints

- **The baseline invariant is sacred.** `Baseline(commit, files)` must always satisfy: the skill's content at `commit` hashes exactly to `files`. A file copy may only happen when a matching baseline is constructible — never refresh hashes without a commit, nor a commit without matching hashes. This supersedes s08t3701's edge-case note ("when the latest commit cannot be resolved, keep prior behavior"), which copied files while leaving a stale/mismatched baseline.

- **Resolve the verified commit before copying.** Move `latest_commit` resolution to the top of `_update_skill`, before the provider loop, so the side-effecting copy never runs unless the commit is verified. *Rejected: copy-then-rollback (fragile restore of files we should never have touched).*

- **`resolve_verified_commit` raises instead of returning `None`.** It now raises `AppError(reason, props=...)` built from the `CommitVerification` result (and a separate "no commit found for `<rel_path>`" when `get_skill_commit` is empty). Callers update accordingly:
  - `_install._resolve_commit` → simplifies to a direct call; its hand-built "content does not match commit" message is removed.
  - `_update.py` → the raise propagates through `_run_updates`' existing `try/except` (`[red]failed[/red]` + `render_error`), so the skill is **not** re-registered: files AND baseline stay as they were.
  - `_update_attach._attach_one` → keeps its intentional "try-or-skip" probe: wrap the call in `try/except AppError`, call `console.debug_traceback()` (so the reason surfaces under `--debug`), and `return None`. Mirrors the existing `except AppError: console.debug_traceback()` pattern at `_update_attach.py` (broken-source skip).

- **Committed-but-dirty source → error.** Source working tree matches no commit for the path (uncommitted/extra/missing files) or no commit touches the path → the raised `AppError` aborts that skill. *Rejected: silently keeping the old baseline after the copy (the original half-apply bug).*

- **Source unavailable (pull failed) → skip, not error.** When `source_repos`/`source_branches` lack the skill's source (because `_pull_sources` hit a pull failure, already reported once at source level), short-circuit `_update_skill` before the copy loop and report `[yellow]skipped[/yellow] [dim](source unavailable)[/dim]` via a skill-level flag on `_SkillReport`. Baseline/files untouched; `register_skill` is called with the unchanged baseline/detached (or skipped). Never `up-to-date`, never a redundant per-skill error. *Rejected: a per-skill `AppError` for every skill of the failed source (N duplicate errors burying the one real cause).*

- **`_advance_baseline` simplification.** With resolve-before-copy + raise, the `in_sync and latest_commit is None` branch is unreachable (an in-sync skill always has a verified commit or we raised earlier). Remove that branch.

## Edge cases

- Source working tree has an uncommitted edit to the skill → `update` reports `failed` naming the first offending file; nothing copied; manifest entry unchanged. `install` reports the same precise error.
- No commit touches the skill's path → "no commit found" error; same no-op outcome.
- Source pull failed (offline is NOT this case — offline still records the repo) → skill reported `skipped (source unavailable)`, baseline/files untouched.
- Fresh install target (`dst` absent) but source is dirty/uncommitted → still must not copy; the pre-copy resolution raises first.
- `_update_attach` candidate whose content doesn't match any source commit → silently not attached (as today), with the reason visible under `--debug`.
- In-sync skill with a resolvable commit → unchanged happy path: baseline advances atomically (s08t3701 behavior preserved).

## Key files

- `src/repo_skills/git.py` — `resolve_verified_commit` raises `AppError` (no-commit and content-mismatch cases) using the `CommitVerification.reason`/`.props` from s08t3703; no longer returns `None`.
- `src/repo_skills/cli/_update.py` — reorder `_update_skill` (resolve before the provider loop); add the source-unavailable short-circuit + skill-level flag on `_SkillReport`; add the `skipped (source unavailable)` label and render it in `_print_skill_report`; simplify `_advance_baseline`.
- `src/repo_skills/cli/_install.py` — simplify `_resolve_commit` to a direct call (drop the manual message).
- `src/repo_skills/cli/_update_attach.py` — wrap `resolve_verified_commit` in `try/except AppError: console.debug_traceback(); return None`.
- `tests/cli/helper.py`, `tests/cli/test_update*.py`, `tests/cli/test_install.py`, `tests/cli/test_update_attach.py` — update expectations: dirty-source now errors (not silently keeps old baseline); add source-unavailable skip coverage; attach still skips quietly.

## Acceptance criteria

- Updating a skill whose source working tree doesn't match any commit reports `failed` with a message naming the first offending file; no provider install dir is modified and the manifest baseline is unchanged.
- `install` of such a skill raises the same precise error (offending file named) and writes no manifest entry.
- A skill whose source pull failed is reported `skipped (source unavailable)` (not `up-to-date`, not a per-skill error); its files and baseline are untouched.
- An untracked install dir whose content matches no source commit is still not auto-attached, and the reason is printed only under `--debug`.
- The in-sync atomic-advance happy path from s08t3701 is unchanged; the `in_sync and latest_commit is None` branch is gone from `_advance_baseline`.
- `uv run tox` is green (all environments), including pre-existing issues.
