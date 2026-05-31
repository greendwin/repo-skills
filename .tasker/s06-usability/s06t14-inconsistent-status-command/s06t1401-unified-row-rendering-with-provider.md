---
id: s06t1401
slug: unified-row-rendering-with-provider
status: done
---

# Unified row rendering with provider grouping

## Goal

All skill rows (installed, available, mergeable, orphan) render in a uniform `name providers status` layout, with providers comma-joined when they share the same status.

## Decisions & constraints

- **Uniform three-column layout** — no parenthetical hints. The old `_untracked_hint` / `UntrackedLookup` / `_build_untracked_lookup` machinery becomes unnecessary and should be removed.
- **Group by status, comma-join providers** — when multiple providers share the same status for a skill, they're comma-joined on one line. Different statuses get separate lines.
- **Available skills** (no provider copy) render with an empty provider column.
- **Orphan section** uses the same grouping logic.
- Status labels stay unchanged (`synced`, `modified`, `outdated`, `untracked`, `mergeable`, `available`, `orphan`, `missing`).

## Key files

- `src/repo_skills/cli/_status.py` — refactor `_print_source_sections`, `_print_untracked_section`, remove `_untracked_hint` / `_build_untracked_lookup` / `UntrackedLookup`
- `tests/cli/test_status.py` — update `TestStatusUntrackedHint`, `TestStatusMultiProvider`, `TestStatusMergeable` to assert the new column format

## Acceptance criteria

- Installed skill with two providers, same status: one line with comma-joined providers
- Installed skill with two providers, different statuses: two lines, one per status group
- Mergeable skill shows `name provider mergeable` (no parenthetical)
- Available skill (not in any provider) shows `name <blank> available`
- Orphans with multiple providers comma-join on one line
- Existing tests for synced/modified/missing/outdated/broken still pass
