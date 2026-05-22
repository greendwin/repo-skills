---
id: s07t0201
slug: orphan-merge-simple-copy-path
status: done
---

# Orphan merge (simple copy path)

## Goal

Allow merging orphan skills (in provider dir, no matching source) via a simple copy-to-source path. No merge branch machinery — just copy files to skills dir on pinned branch, commit (or `--no-commit`), create manifest entry.

## Decisions & Constraints

- **Auto-pick source if one registered, require `--source` if multiple.** Orphan skills have no source association, so the user must tell us where to put them when ambiguous.
- **Separate simpler path than the merge branch flow.** Switch to pinned branch, copy files, commit (or keep as-is with `--no-commit`). No merge branch, no rebase. *Rejected: reusing merge branch machinery (unnecessary complexity for a simple copy).*
- **Installed files are never deleted without explicit user action.** The provider copy stays intact.
- **Manifest entry created after merge.** The skill becomes fully tracked with correct commit and hashes.

## Key files

- `src/repo_skills/cli/_merge.py` — add orphan merge path
- `tests/cli/test_merge.py` — tests

## Acceptance criteria

- Orphan skill with single source: auto-picks source, copies files, commits, creates manifest entry
- Orphan skill with multiple sources and no `--source`: error with guidance
- Orphan skill with `--source`: copies to specified source
- `--no-commit` leaves files staged without committing
- Manifest entry created with correct commit and hashes after merge
