---
id: s06t0901
slug: build-untracked-lookup-and-pass
status: done
---

# Build untracked lookup and pass to rendering

## Goal

Build a `dict[str, list[str]]` mapping skill name → provider names with untracked copies in `status()`, and thread it through to `_print_source_sections()`. No visible output change yet — this is the plumbing.

## Decisions & Constraints

- **Build lookup dict upfront in `status()`** — after `_collect_untracked()` runs, derive a dict from the existing `untracked` list. Entries where `source_match` is non-empty are mergeable and should be included. *Rejected: computing inside each section renderer (duplicates logic).*
- Must not break any existing tests.

## Key files

- `src/repo_skills/cli/_status.py`
- `tests/cli/test_status.py`

## Acceptance criteria

- `_collect_untracked()` result is used to build a `dict[str, list[str]]` mapping skill name → list of provider names
- `_print_source_sections()` accepts the new lookup parameter
- All existing tests pass unchanged
