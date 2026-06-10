---
id: s06t1303
slug: guards-and-error-wording
status: pending
---

# Guards and error wording

## Goal

Implement the failure/edge paths for auto-detect: in-progress-merge short-circuit, ambiguous-layer error, and all-empty error — replacing the old "Skill name is required." message.

## Decisions & constraints

- **Short-circuit on in-progress merge** — before scanning layers, if any source repo has a `skill-merge/...` branch, raise an error with the `--continue`/`--abort` nudge (preserves the spirit of the old hint). Reuse `_has_merge_branch`. Prevents starting a second, unrelated merge while one is half-finished.
- **Ambiguous layer** — when the first non-empty layer has >1 candidate, raise `AppError` listing them, e.g. `Multiple modified skills (grill-me, to-tasks). Specify which to merge.` with hint `Run skills merge <skill> to choose.`; substitute the tripped layer's name (modified/mergeable/orphan).
- **All layers empty** — raise `NoopError`: `Nothing to merge — no modified, mergeable, or orphan skills found.`
- Reuse the file's existing `AppError`/`NoopError` patterns and console formatting helpers.

## Edge cases

- In-progress merge exists in a source repo not under cwd — `_detect_merge_repo`/`_has_merge_branch` semantics apply.
- Two modified skills -> ambiguous error names both, sorted.
- Nothing installed / everything synced -> NoopError, not a crash.
- Ordering of candidate names in the error message is deterministic (sorted).

## Key files

- `src/repo_skills/cli/_merge.py` (`merge` command auto-detect entry; reuse `_has_merge_branch`)
- `tests/cli/test_merge.py` (use `assert_invoke`)

## Acceptance criteria

- Bare `skills merge` with a `skill-merge/...` branch present errors with the `--continue`/`--abort` nudge and does not start a new merge.
- Bare `skills merge` with >1 candidate in the first non-empty layer raises the listing `AppError` (names sorted, correct layer noun).
- Bare `skills merge` with no candidates in any layer raises the `NoopError` with the specified message.
- Old "Skill name is required." path is gone.
- `uv run tox` passes (all environments).
