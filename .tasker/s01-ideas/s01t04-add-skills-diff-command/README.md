---
id: s01t04
slug: add-skills-diff-command
status: pending
---

# Add 'skills diff' command

## Decisions

- **Baseline vs. installed copy** — diff shows what the user changed locally since install/update, not upstream drift
- **Read baseline from source repo at `entry.commit`** — manifest only stores hashes; source repo has actual content; infrastructure exists in `_merge.py`
- **Untracked mergeable skills diff against source HEAD** — no commit recorded, so current source content is the best baseline
- **Orphaned skills → `AppError`** — no source to diff against, error is the only option
- **Unified diff with Rich coloring** — `+` green, `-` red, `@@` cyan via `echo()`; consistent with CLI patterns and ADR 0001
- **Single skill name argument** — keep it simple; multiple-skill diff is noisy
- **`NoopError` when not modified** — consistent with merge's "already synced" pattern
- **Full add/remove for new/deleted files** — standard unified diff behavior
- **Extract `_find_in_provider` and `_resolve_untracked` to shared module** — reusable helpers shouldn't live in `_merge.py`
- **Include `--from` flag** — provider disambiguation, same pattern as merge
- **Error when source repo unavailable** — a diff that can't show a diff isn't useful

## Subtasks

- [ ] [s01t0401](s01t0401-extract-shared-helpers-from-mergepy.md): Extract shared helpers from _merge.py
- [ ] [s01t0402](s01t0402-basic-diff-command-for-tracked.md): Basic diff command for tracked modified skill
- [ ] [s01t0403](s01t0403-edge-cases-not-modified-addeddeleted.md): Edge cases: not modified, added/deleted files, errors
