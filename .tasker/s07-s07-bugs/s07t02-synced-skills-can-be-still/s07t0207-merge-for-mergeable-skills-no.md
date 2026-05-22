---
id: s07t0207
slug: merge-for-mergeable-skills-no
status: pending
---

# Merge for mergeable skills (no manifest entry)

## Goal

Allow merging skills that exist in a provider dir and match a source skill by name but have no manifest entry. Compute hashes from installed copy, search for base commit, create manifest entry.

## Decisions & Constraints

- **Exact hash match is not a no-op — the manifest entry must be created.** Tracking is the whole point. The skill goes from untracked to tracked even if files already match a commit. *This is different from the existing no-op check in `_finalize` which compares against `entry.files`.*
- **Close match uses normal merge flow.** Found base commit is used to create merge branch, standard merge/rebase proceeds.
- **No match falls through to orphan branch + rebase_root.** Existing fallback path.
- **Hashes computed from installed copy.** No stored baseline exists, so current installed files are the only reference for search.

## Key files

- `src/repo_skills/cli/_merge.py` — extend `_resolve_untracked` or add new path for mergeable skills
- `tests/cli/test_merge.py` — tests

## Acceptance criteria

- Mergeable skill with exact commit match: manifest entry created, "already up to date" message
- Mergeable skill with close match: normal merge flow with found base commit
- Mergeable skill with no match: orphan branch + rebase_root flow
