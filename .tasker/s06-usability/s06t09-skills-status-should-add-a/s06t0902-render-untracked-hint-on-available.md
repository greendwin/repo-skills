---
id: s06t0902
slug: render-untracked-hint-on-available
status: done
---

# Render untracked hint on available and installed skills

## Goal

Available and installed skill lines show `(untracked in <providers>)` in `[dim]` when the lookup has entries for that skill.

## Decisions & Constraints

- **Label text: `(untracked in claude, cursor)`** — appended after the status, dim styling. Short and actionable. *Rejected: `(has local copy)` (doesn't say which provider); replacing status entirely (loses available/synced info).*
- **Dim color for the hint** — `[dim]` styling so it doesn't compete with status labels. *Rejected: `[cyan]` (visual confusion with status); `[yellow]` (implies warning when it's informational).*
- **Multiple providers comma-separated** — on a single line. *Rejected: repeating the skill line per provider; showing only the first.*
- **Show hints on both available and installed skills** — an untracked copy in another provider is worth surfacing regardless of install status. *Rejected: available-only (misses stray copies in other providers for installed skills).*

## Key files

- `src/repo_skills/cli/_status.py`
- `tests/cli/test_status.py`

## Acceptance criteria

- An available skill with an untracked counterpart shows `available` followed by `(untracked in <provider>)`
- An installed skill with an untracked copy in another provider shows the hint after its status
- Multiple providers are comma-separated
- Skills without untracked counterparts render unchanged
