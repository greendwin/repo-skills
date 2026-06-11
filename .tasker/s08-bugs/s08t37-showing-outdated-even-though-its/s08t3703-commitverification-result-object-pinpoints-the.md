---
id: s08t3703
slug: commitverification-result-object-pinpoints-the
status: pending
---

# CommitVerification result object pinpoints the first content mismatch

## Goal

`verify_commit_content` stops returning a bare `bool` and instead returns a `CommitVerification` dataclass that reports whether the working tree matches a commit and, when it does not, names the **first** offending file. This slice is purely additive: `resolve_verified_commit` consumes the new `.matches` field internally but keeps its current external contract (returns the commit string or `None`), so no caller changes and no user-facing behavior changes yet. The deliverable is the new git capability with direct unit coverage.

## Decisions & constraints

- **Precise verification detail via a result object.** Define in `git.py`, next to the `GitRepo` Protocol (its return type):

  ```python
  @dataclass(frozen=True)
  class CommitVerification:
      matches: bool
      reason: str | None = None                            # display message
      props: dict[str, str] = field(default_factory=dict)  # e.g. {"file": ..., "repo": ...}
  ```

  `matches` is the authoritative flag; `reason` is a friendly display message; `props` carries structured extras that map 1:1 onto `AppError(message, *, props=dict[str, str])`. *Rejected: bare `bool` (no actionable detail); encoding ok/fail in a `str | None` (state in a primitive).*

- **First offending file only — keep the message compact.** `verify_commit_content` returns at the first problem it finds, classifying it as one of: `not present in commit` (empty `ls-tree` listing), `missing file '<f>'` (a committed file absent locally), `file '<f>' differs` (committed file content differs), `untracked file '<f>'` (first of `sorted(local - committed)`). `props` includes the offending file and the repo path. *Rejected: enumerating all offending files — only the first is reported this round (see parent Out of scope).*

- **Additive only.** `resolve_verified_commit` switches its internal check from `if not git.verify_commit_content(...)` to `if not result.matches`, but still returns `str | None` exactly as today. Raising is deferred to the next slice so this one stays green with no caller edits.

- **Line-ending normalization stays consistent.** The real impl keeps using `normalize_line_endings` for both committed content and local bytes, so CRLF/LF differences don't produce false mismatches (mirror the existing logic in `verify_commit_content`).

## Edge cases

- Working tree matches exactly → `CommitVerification(matches=True, reason=None, props={})`.
- Committed file missing locally → `matches=False`, reason `missing file '<f>'`.
- Committed file content differs (after normalization) → `file '<f>' differs`.
- Extra local file not in the commit tree → `untracked file '<f>'` (first in sorted order).
- Empty `ls-tree` listing (path not present in commit) → `not present in commit`.
- CRLF-vs-LF only difference → still `matches=True` (normalization).

## Key files

- `src/repo_skills/git.py` — add `CommitVerification`; change the `GitRepo.verify_commit_content` Protocol signature to `-> CommitVerification`; update `resolve_verified_commit` to read `.matches` (contract unchanged: still returns `str | None`).
- `src/repo_skills/git_real.py` — `RealGitRepo.verify_commit_content` builds and returns `CommitVerification` with the first-problem reason + props (reuse `ls-tree`, `get_file_at_commit`, `normalize_line_endings`).
- `tests/cli/helper.py` — `FakeGitRepo.verify_commit_content`: keep the `verified: dict[str, bool]` toggle but map it to `CommitVerification(matches=ok, reason=None if ok else "content mismatch")`, so the existing `_fake_git.verified[...] = False` setups in `test_install.py`, `test_update.py`, `test_update_attach.py` keep working.
- `tests/test_git_real.py` — switch `verify_commit_content(...) is True/False` assertions to `.matches`, and add assertions on `.reason`/`.props` for each mismatch class (missing / differs / untracked / not-present).

## Acceptance criteria

- `verify_commit_content` returns `CommitVerification`; `.matches` is `True` for an exact match and `False` otherwise.
- For each mismatch class, `.reason` names the first offending file and `.props` contains that file plus the repo path; only the first problem is reported even when several files are wrong.
- A CRLF-vs-LF-only difference still yields `matches=True`.
- `resolve_verified_commit` behaves exactly as before (returns the commit or `None`); no caller or CLI-output change in this slice.
- `uv run tox` is green (all environments), including pre-existing issues.
