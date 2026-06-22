---
id: s08t2303
slug: source-init-branching-skillsdir-flag
status: done
---

# Source init branching + --skills-dir flag

## Goal

`skills source init` behaves per the three detection cases, and a new repeatable `--skills-dir` option lets the user supply the dir list explicitly (bypassing detection). Reinit reconciles a changed `--skills-dir` like it does name/branch.

## Decisions & constraints

- **Three-case branching** — Consume the typed `DetectResult` from the detection slice:
  - NONE → keep the current fresh-repo behavior: create `skills/` with a `.gitkeep`, set `skills_dirs=["skills"]`.
  - SINGLE → `skills_dirs = [<detected dir, repo-relative POSIX>]`.
  - AMBIGUOUS → **raise `AppError`** telling the user skills are spread across the repo root and to re-run with explicit `--skills-dir` values. Do NOT auto-create or guess. *Rejected: auto-detecting the multi-dir list — categories make a skill's parent an unreliable signal, and silently scanning large parts of the repo is the wrong-guess behavior we're removing.*
- **`--skills-dir` flag** — Repeatable typer option producing `list[str]`, e.g. `skills source init --skills-dir claude/skills --skills-dir copilot`. When one or more values are given, **skip detection entirely** and use them verbatim, normalized to repo-relative POSIX. *Rejected: a single comma-separated value (escaping problems, less clear).*
- **Validation of explicit list** — Reject only paths that escape the repo (absolute paths outside the repo root, or `../` traversal). Do NOT require a dir to exist or to already contain a `SKILL.md`: the first dir doubles as the merge target (`merge` creates it on demand) and a user may name dirs ahead of populating them. A soft (dim) note when a listed dir currently has no skills is acceptable; it must not fail. `--skills-dir .` (repo root) is allowed.
- **Reinit reconciles `--skills-dir`** — In `_handle_reinit`, treat `--skills-dir` like name/branch: if the given list differs from stored `skills_dirs`, update it and report the change (`dirs: [...] → [...]` using `fmt_data`). When `--skills-dir` is omitted on reinit, leave the stored list untouched and do NOT re-detect (matches today's behavior where reinit never touches the dir).

## Edge cases

- AMBIGUOUS on a *fresh* init writes no config (errors before `save_source_config`); a follow-up `--skills-dir` run is therefore a fresh init, not a reinit.
- Explicit `--skills-dir` on a fresh init bypasses detection even when the repo would have been SINGLE or AMBIGUOUS.
- Empty repo + explicit `--skills-dir` → use the given list, do not create the default `skills/` `.gitkeep`.
- Reinit with `--skills-dir` identical to stored list → no change reported.

## Key files

- `src/repo_skills/cli/_source.py` — `source_init`, `_handle_reinit`, `DEFAULT_SKILLS_DIR`, `GIT_KEEP_FILE`.
- `src/repo_skills/discovery.py` — `detect_skills_dir` (typed result from prior slice).
- `src/repo_skills/utils.py` — `rel_posix`, `write_text`; repo-escape check helper if one exists.
- Tests: `tests/cli/test_source_init.py` (`test_detects_existing_skills_dir`, the default-`skills` assertions, etc.), `tests/cli/helper.py` `assert_invoke`.

## Acceptance criteria

- Fresh init in a repo with skills under a single dir below root → `skills_dirs` is that one dir; no `.gitkeep` created.
- Fresh init in a repo with skills straddling the root → command errors with a message mentioning `--skills-dir`; no `source.json` written.
- Fresh init in an empty repo → creates `skills/.gitkeep`, `skills_dirs == ["skills"]`.
- `--skills-dir a --skills-dir b` → `skills_dirs == ["a", "b"]`, detection not consulted.
- `--skills-dir ../outside` or an absolute path outside the repo → errors.
- Reinit with a new `--skills-dir` list updates `skills_dirs` and reports `dirs:` change; reinit without it leaves the list unchanged.
- Uses `assert_invoke` (not `CliRunner`), `monkeypatch` (not `patch`), pyfakefs. `uv run tox` green.
