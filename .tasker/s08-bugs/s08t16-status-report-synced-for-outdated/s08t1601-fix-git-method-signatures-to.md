---
id: s08t1601
slug: fix-git-method-signatures-to
status: done
---

# Fix git method signatures to accept rel_path

## Goal

Git methods accept `skill_rel_path` instead of `skill_name`, and `get_skill_commit` supports an optional `branch` parameter. All existing callers updated. Existing behavior must not change.

## Decisions & constraints

- **Replace `skill_name` with `skill_rel_path`** — `get_skill_commit` and `verify_commit_content` hardcode `f"skills/{skill_name}"`, which breaks for categorized skills (e.g. `skills/workflow/tdd`). Change both to accept the actual relative path. The `rel_path` is already available via `SourceSkill.rel_path` at all call sites. *Rejected: keeping `skill_name` and guessing the path.*
- **Add optional `branch` parameter to `get_skill_commit`** — signature becomes `get_skill_commit(self, skill_rel_path: str, *, branch: str | None = None)`. When `branch` is provided, run `git log -1 --format=%H <branch> -- <path>`. When `None`, use current HEAD (existing behavior).
- Must update: `GitRepo` protocol (`git.py`), `RealGitRepo` (`git_real.py`), `FakeGitRepo` (`tests/cli/helper.py`), and all callers in `_install.py` and `_merge.py`.

## Edge cases

- `verify_commit_content` also builds `self._path / skill_path` for local file comparison — must use `rel_path` there too.
- `FakeGitRepo.commits` dict is keyed by `skill_name` — callers will now pass `rel_path`, so test setups need updating.

## Key files

- `src/repo_skills/git.py` — GitRepo protocol
- `src/repo_skills/git_real.py` — RealGitRepo implementation
- `tests/cli/helper.py` — FakeGitRepo
- `src/repo_skills/cli/_install.py` — `_resolve_commit` caller
- `src/repo_skills/cli/_merge.py` — multiple callers

## Acceptance criteria

- `get_skill_commit("skills/category/tdd")` queries the correct path (no double `skills/` prefix)
- `get_skill_commit("skills/tdd", branch="main")` produces `git log -1 --format=%H main -- skills/tdd`
- `get_skill_commit("skills/tdd")` (no branch) behaves as before
- All existing tests pass with updated signatures
