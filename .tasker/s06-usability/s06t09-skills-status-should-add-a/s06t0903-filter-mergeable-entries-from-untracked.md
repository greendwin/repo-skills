---
id: s06t0903
slug: filter-mergeable-entries-from-untracked
status: done
---

# Filter mergeable entries from Untracked section

## Goal

Untracked section no longer shows mergeable entries — only orphans remain.

## Decisions & Constraints

- **Remove mergeable from Untracked** — the hint on the source-section line makes it redundant. Untracked section shows only orphans. *Rejected: keeping both (duplicate noise).*
- Orphan rendering must remain unchanged.
- If all untracked entries were mergeable, the Untracked section should not appear at all.

## Key files

- `src/repo_skills/cli/_status.py`
- `tests/cli/test_status.py`

## Acceptance criteria

- Mergeable entries no longer appear in the Untracked section
- Orphan entries still appear as before
- Untracked section header is hidden when no orphans exist
- Existing `TestStatusMergeable` test is updated to verify the hint appears in the source section instead
- `TestStatusUntrackedOrdering` test is updated (only orphans remain)
