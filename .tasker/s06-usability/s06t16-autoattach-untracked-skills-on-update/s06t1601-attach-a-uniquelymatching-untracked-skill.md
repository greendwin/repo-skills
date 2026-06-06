---
id: s06t1601
slug: attach-a-uniquelymatching-untracked-skill
status: in-review
---

# Attach a uniquely-matching untracked skill

## Goal

During `update`, an untracked provider dir whose file hashes exactly match a source skill at pinned-branch HEAD is registered into the manifest (attached) and updated, printing `Attached skill X (matched source Y)`. Modified copies stay untouched. The single-source case is the tracer bullet; ambiguity/filter integration is the next slice.

## Decisions & constraints

- **Matching** — match the installed copy's file hashes against the source skill's content at pinned-branch HEAD (the same content `update` would copy).
- **Baseline** — on attach, record baseline as that skill's commit + source hashes, mirroring `install` (`_record_manifest` / `_resolve_commit`). Set `detached=False`.
- **Manifest-only** — no file writes during attach itself; subsequent per-provider update logic syncs files.
- Remove the existing `_update.py` TODO ("can we do anything with skills that are not in manifest?").

## Edge cases

- A modified untracked copy (hashes differ) → not attached, left untouched.

## Key files

- `src/repo_skills/cli/_update.py`
- `tests/cli/test_update.py`

## Acceptance criteria

- An exact-match untracked skill becomes managed (manifest entry with correct baseline) and is updated; `Attached skill X (matched source Y)` is printed.
- A modified untracked copy is not attached and its files are untouched.
- The `_update.py` TODO is gone.
