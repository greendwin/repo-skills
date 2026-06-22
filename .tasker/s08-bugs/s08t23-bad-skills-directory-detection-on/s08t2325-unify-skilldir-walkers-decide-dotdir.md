---
id: s08t2325
slug: unify-skilldir-walkers-decide-dotdir
status: in-review
---

# Unify skill-dir walkers + decide dot-dir pruning policy

## Context

There are two hand-rolled `os.walk` loops that both answer "find the outermost `SKILL.md` dirs under a root", and they have silently diverged:

- `discovery._iter_skill_dirs` (`src/repo_skills/discovery.py`) prunes dot-directories (`dirnames[:] = [d for d in dirnames if not d.startswith(".")]`) before checking for `SKILL_FILE`, then `dirnames.clear()` at the outermost `SKILL.md`. Used by `detect_skills_dir` / `has_any_skill`.
- `_collect_source_skills` (`src/repo_skills/config/_source.py`) does the same walk + `dirnames.clear()` but does NOT prune dot-dirs.

Consequence: a `SKILL.md` under a hidden dir (e.g. `skills/.archive/foo/SKILL.md`) is collected as a real skill by `load_source` but is invisible to detection — the set of skills a source "detects" differs from the set it "collects". This is both true duplication (one rule expressed twice) and a behavioral inconsistency that can produce false collisions.

Deferred from the dev-loop on s08t2304 (refactor phase) because aligning the pruning is a behavior change, not a behavior-preserving refactor.

## Decisions to make

- **Canonical dot-dir policy** — almost certainly: collection should prune hidden dirs to match detection (you don't want `.venv`/`.tox`/`.archive` skills). Confirm this is intended, then align.
- **Where the shared walker lives** — `discovery` already imports `from .config import SKILL_FILE`, so `config/_source.py` cannot import from `discovery` (cycle). Put a shared `iter_skill_dirs(root)` generator in the config layer (e.g. `config/_skill_md.py` next to `SKILL_FILE`); have both `discovery._iter_skill_dirs` and `_collect_source_skills` consume it.

## Approach

- Extract the walk (os.walk → prune dot-dirs → `dirnames.clear()` on `SKILL_FILE` → yield `Path(dirpath)`) into one config-layer generator.
- `detect_skills_dir`/`has_any_skill` delegate to it (no behavior change there).
- Rewrite `_collect_source_skills`' inner loop as `for skill_dir in iter_skill_dirs(skills_root): name = skill_dir.name; rel_path = rel_posix(skill_dir, repo_root); ...` — this deletes the second walk AND aligns dot-pruning.

## Acceptance criteria

- A single shared walker; `_collect_source_skills` no longer re-implements `os.walk`.
- Collection and detection agree on hidden-dir handling (add a test: `SKILL.md` under a dotted subdir is NOT collected).
- Existing collision/multi-dir tests still green.
- `uv run tox` green.

## Out of scope

- Nested/overlapping `skills_dirs` normalization collapse (separate follow-up).
