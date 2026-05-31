---
id: s01t0403
slug: edge-cases-not-modified-addeddeleted
status: in-progress
---

# Edge cases: not modified, added/deleted files, errors

**Goal:** Handle remaining cases for the diff command.

**Decisions:**
- `NoopError` when skill is not modified (synced)
- Full add/remove for new/deleted files (all `+` or all `-` lines)
- Orphaned skills → `AppError` (no source to diff against)
- Source repo unavailable → `AppError`
- Untracked mergeable skills diff against source HEAD (no commit recorded)

**Key files:** `src/repo_skills/cli/_diff.py`, `tests/cli/test_diff.py`
