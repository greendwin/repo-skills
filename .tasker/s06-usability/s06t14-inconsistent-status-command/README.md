---
id: s06t14
slug: inconsistent-status-command
status: done
---

# Inconsistent 'status' command -

## Context

The `status` command renders "untracked" skills in two inconsistent visual styles: bare label (`grill-me claude untracked`) vs parenthetical hint (`commit-summary mergeable (untracked in claude)`). Both represent the same logical state but look different. The fix is to unify all skill rows to a single `name providers status` column layout with provider grouping by status.

## Decisions

- **Uniform `name providers status` column layout** — all skill rows (installed, available, mergeable, orphan) use the same three-column format. No parenthetical hints. *Rejected: renaming one of the "untracked" labels (they're both logically correct); unifying only the visual style while keeping parenthetical format (inconsistent with installed rows).*
- **Group by status, comma-join providers** — when multiple providers share the same status for a skill, they're comma-joined on one line. Different statuses get separate lines. *Rejected: one line per provider always (redundant for common case); single line with comma-joined providers ignoring status differences (loses information).*
- **Available skills render with empty provider column** — skills not in any provider show a blank provider column rather than a dash or placeholder. *Rejected: dash placeholder (visual noise for no information gain).*
- **Orphan section uses same grouping** — the `Untracked` section applies identical group-by-status rendering. Orphans only have one status so they always comma-join.

## Open questions

None.

## Out of scope

- No changes to the status labels themselves (`synced`, `modified`, `outdated`, `untracked`, `mergeable`, `available`, `orphan`, `missing`).
- No changes to the `Untracked` section header or when it appears.

## Subtasks

- [x] [s06t1401](s06t1401-unified-row-rendering-with-provider.md): Unified row rendering with provider grouping
