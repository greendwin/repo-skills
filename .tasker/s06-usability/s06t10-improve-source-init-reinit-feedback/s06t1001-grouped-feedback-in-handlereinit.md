---
id: s06t1001
slug: grouped-feedback-in-handlereinit
status: done
---

# Grouped feedback in `_handle_reinit`

## Goal

`_handle_reinit` reports changes as indented detail lines under the appropriate header.

## Decisions

- **Grouped output format** — `key: old → new` indented under header
- **"Updated" header** — `Updated source X.` when something changed; `Source X already initialized.` only for true no-op
- **Rename folded in** — `name: foo → bar` as a detail line
- **Re-registered keeps distinct header** — `Registered source X.` with detail lines underneath if applicable

## Key files

- `src/repo_skills/cli/_source.py` — `_handle_reinit()` (lines 49-89)
- `tests/cli/test_source_init.py` — update existing tests, add new ones for branch change feedback
