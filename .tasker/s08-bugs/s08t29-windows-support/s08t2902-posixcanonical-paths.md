---
id: s08t2902
slug: posixcanonical-paths
status: done
---

# POSIX-canonical paths

## Goal

Skill paths produced/stored on a `\`-separator OS match git output and hash-map keys, so `ls-tree`/`ls-files` resolve and `verify_commit_content`'s file-set comparison succeeds on Windows. Establishes the invariant: any path stored in config/manifest or compared against git output is forward-slash (POSIX).

## Decisions & constraints

- **POSIX is the path invariant** — canonicalize to forward slashes at every serialization/comparison point, not just at the git boundary. Fixes hash-map keys, manifest portability, and git interop together. Rejected converting only at the git boundary (leaves hash-key and config-portability bugs unfixed, scatters conversions across every git call site).
- **Add `to_posix(path) -> str` to `repo_skills/utils.py`**, implemented as `str(path).replace("\\", "/")`. This is the only implementation that is both production-correct on Windows AND deterministically testable on Linux CI. Rejected `PurePath.as_posix()`: on Linux `Path("skills\\tdd").as_posix()` leaves the backslash untouched, so it can't be exercised by a plain Linux test and behaves differently for str/PurePosixPath/PureWindowsPath inputs. Accepts `str` and `Path` uniformly. Caveat: a genuine backslash in a Linux filename (legal but pathological for skill dirs) would be rewritten — acceptable in this domain.
- **Apply at all four sites:**
  - `config/_utils.py` `compute_file_hashes` — rel-path keys (`str(full.relative_to(skill_dir))`).
  - `git_real.py:252` — the `local_files` set built from `rglob` (compared against `git ls-tree` output, which is already POSIX).
  - `config/_source.py:96` — `rel_path = os.path.relpath(dirpath, repo_root)` (handed to git `ls-tree`/`ls-files` and stored in manifest).
  - `cli/_source.py:64` — `skills_dir = str(skills_dir.relative_to(...))` (later interpolated as `f"{skills_dir}/{skill_name}"`).
- **No migration** — no-op on Linux/macOS; Windows was already broken so no valid stored paths to preserve.

## Edge cases

- On Linux, native paths already use `/` → `to_posix` is a no-op, so existing behavior and baselines are unchanged.
- `verify_commit_content` set comparison: `git ls-tree` emits `/`; the local set must be POSIX-normalized to match — without this it never compares equal on Windows regardless of content.
- Mixed-separator interpolation (`f"{skills_dir}/{skill_name}"`) — fixed by storing `skills_dir` POSIX.

## Key files

- `src/repo_skills/utils.py` — new `to_posix` (beside `normalize_newlines` from slice 1).
- `src/repo_skills/config/_utils.py`, `src/repo_skills/git_real.py`, `src/repo_skills/config/_source.py`, `src/repo_skills/cli/_source.py` — apply `to_posix`.
- Tests: a direct unit test for `to_posix` feeding a `PureWindowsPath("skills\\tdd")` / literal-backslash string and asserting `"skills/tdd"`; assertions that `compute_file_hashes` keys and the `config/_source.py` `rel_path` are forward-slash.

## Acceptance criteria

1. `to_posix` converts a backslash-separated input (`PureWindowsPath("skills\\tdd")` or literal `"skills\\tdd"`) to `"skills/tdd"`, and leaves a `/`-separated input unchanged — verified on Linux CI.
2. `compute_file_hashes` for a nested skill produces forward-slash keys (e.g. `subdir/file.md`).
3. `config/_source.py` populates `SourceSkill.rel_path` in POSIX form for nested skills.
4. `uv run tox` (all environments) is green, including any pre-existing issues.
