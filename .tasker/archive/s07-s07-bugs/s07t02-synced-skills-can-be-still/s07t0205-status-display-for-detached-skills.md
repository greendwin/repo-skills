---
id: s07t0205
slug: status-display-for-detached-skills
status: done
---

# Status display for detached skills

## Goal

Make `skills status` exclude detached skills from the installed display so they appear as mergeable or orphan through existing logic.

## Decisions & Constraints

- **Detached entries excluded from `installed_by_source`.** They fall through to `_collect_untracked` / `_scan_sources` and appear as mergeable (if name matches a source skill) or orphan (if source removed). No new UI concept.
- **No special display.** Detached skills look identical to regular mergeable/orphan skills in status output. *Rejected: separate "detached" section or indicator (adds UI complexity for no user benefit).*

## Key files

- `src/repo_skills/cli/_status.py` — exclude detached from `_group_installed_by_source`, ensure `_collect_untracked` doesn't filter them out
- `tests/cli/test_status.py` — tests

## Acceptance criteria

- Detached skills do not appear in the "installed" section of status output
- A detached skill whose name matches a source skill appears as "mergeable"
- A detached skill whose source was removed appears as "orphan"
