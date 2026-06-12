---
id: s08t3703
slug: commitverification-result-object-pinpoints-the
status: done
---

# CommitVerification result pinpoints the first content mismatch

## Goal

`verify_commit_content` stops returning a bare `bool` and instead **raises** a `CommitVerificationError` that names the **first** offending file when the working tree does not match a commit (returning `None` on a match). This slice is purely additive: `resolve_verified_commit` catches the exception and keeps its current external contract (returns the commit string or `None`), so no caller changes and no user-facing behavior changes yet. The deliverable is the new git capability with direct unit coverage.

## Decisions & constraints

- **Precise verification detail via a raised exception.** `verify_commit_content` raises a `CommitVerificationError(AppError)` instead of returning a verdict object. Define it in `git.py`, next to the `GitRepo` Protocol, mirroring the existing `FileNotInCommitError(AppError)`:

  ```python
  class CommitVerificationError(AppError):
      def __init__(self, reason: str, *, repo: str, file: str | None = None) -> None:
          self.reason = reason  # friendly display message
          self.repo = repo      # plain repo path (no markup)
          self.file = file      # first offending file, when one applies
          props = {"repo": repo}
          if file is not None:
              props["file"] = file
          super().__init__(reason, props=props)
  ```

  An exception is the natural shape because failure is the actionable case and the end state (s08t3704) is for `resolve_verified_commit` to propagate it. The typed `reason`/`file`/`repo` attributes give callers actionable detail and the `AppError` props render the message. *Rejected: a `CommitVerification` value object with a `matches: bool` flag (a 4-field object just to say "fine" is noise — `None` for a match is leaner, and `verify` would only ever be checked for failure); a bare `bool` (no actionable detail); a `props: dict[str, str]` bag (untyped/stringly-keyed).*

- **First offending file only — keep the message compact.** `verify_commit_content` raises at the first problem it finds, classifying it as one of: `not present in commit` (empty `ls-tree` listing), `missing file '<f>'` (a committed file absent locally), `file '<f>' differs` (committed file content differs), `untracked file '<f>'` (`min(local - committed)`). The `file` attribute names the offending file and `repo` holds the (plain) repo path. *Rejected: enumerating all offending files — only the first is reported this round (see parent Out of scope).*

- **Additive only.** `resolve_verified_commit` wraps the call in `try / except CommitVerificationError: return None`, but still returns `str | None` exactly as today. Propagation (removing the catch) is deferred to the next slice so this one stays green with no caller edits.

- **Line-ending normalization stays consistent.** The real impl keeps using `normalize_line_endings` for both committed content and local bytes, so CRLF/LF differences don't produce false mismatches (mirror the existing logic in `verify_commit_content`).

## Edge cases

- Working tree matches exactly → returns `None` (no raise).
- Committed file missing locally → raises, reason `missing file '<f>'`.
- Committed file content differs (after normalization) → `file '<f>' differs`.
- Extra local file not in the commit tree → `untracked file '<f>'` (lexically first via `min`).
- Empty `ls-tree` listing (path not present in commit) → `'<rel_path>' not present in commit` (`file` is `None`).
- CRLF-vs-LF only difference → still matches, returns `None` (normalization).

## Key files

- `src/repo_skills/git.py` — add `CommitVerificationError(AppError)`; change the `GitRepo.verify_commit_content` Protocol signature to `-> None`; wrap the call in `resolve_verified_commit` with `try / except CommitVerificationError: return None` (contract unchanged: still returns `str | None`).
- `src/repo_skills/git_real.py` — `RealGitRepo.verify_commit_content` raises `CommitVerificationError` with the first-problem reason + `file`/`repo` (reuse `ls-tree`, `get_file_at_commit`, `normalize_line_endings`).
- `tests/cli/helper.py` — `FakeGitRepo.verify_commit_content`: keep the `verified: dict[str, bool]` toggle but raise `CommitVerificationError("content mismatch", repo=str(self.root))` when not ok (else return `None`), so the existing `_fake_git.verified[...] = False` setups in `test_install.py`, `test_update.py`, `test_update_attach.py` keep working.
- `tests/test_git_real.py` — switch the match assertions to "does not raise", and add `pytest.raises(CommitVerificationError)` cases asserting `.reason`/`.file`/`.repo` for each mismatch class (missing / differs / untracked / not-present).

## Acceptance criteria

- `verify_commit_content` returns `None` on an exact match and raises `CommitVerificationError` otherwise.
- For each mismatch class, the exception's `.reason` names the first offending file, `.file` is that file and `.repo` is the (plain) repo path; only the first problem is reported even when several files are wrong.
- A CRLF-vs-LF-only difference still matches (no raise).
- `resolve_verified_commit` behaves exactly as before (returns the commit or `None`); no caller or CLI-output change in this slice.
- `uv run tox` is green (all environments), including pre-existing issues.
