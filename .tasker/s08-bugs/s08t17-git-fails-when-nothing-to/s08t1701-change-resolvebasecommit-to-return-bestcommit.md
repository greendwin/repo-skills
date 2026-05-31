---
id: s08t1701
slug: change-resolvebasecommit-to-return-bestcommit
status: done
---

# Change `_resolve_base_commit` to return `_BestCommit | None`

## Goal

`_resolve_base_commit` returns `_BestCommit | None` instead of `str | None`, so callers can inspect `.distance`.

## Decisions & constraints

- **Reuse `_BestCommit` as-is** — it's all module-private, no need for a new type. *Rejected: adding a separate boolean return value (parallel signal for same concept).*
- For the manifest-baseline early-return path (line 470 in `_merge.py`), synthesize a `_BestCommit` with a non-zero distance (e.g. `-1`) since we don't search history. The caller only checks `distance == 0`, so any non-zero value works.
- All existing callers in `_merge_start` that use the return value as a string (`base_commit`) must be updated to use `.commit`.
- **Pure refactor** — no behavioral change.

## Key files

- `src/repo_skills/cli/_merge.py` — `_resolve_base_commit`, `_merge_start`
- `tests/cli/test_merge.py` — all existing tests must pass unchanged

## Acceptance criteria

- `_resolve_base_commit` returns `_BestCommit | None`
- All existing callers updated to use `.commit` where they previously used the string directly
- All existing tests pass unchanged
