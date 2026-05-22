---
id: s06t09
slug: skills-status-should-add-a
status: done
---

# 'skills status' should add a label near 'available' skills wwhen they have untracked counterpart

## Context

`skills status` currently shows available/installed skills (from sources) and untracked skills (local directories in providers) in separate sections. When a skill exists both as available/installed in a source and as an untracked directory in a provider, the user sees it in two places with no obvious connection. We need to surface this relationship inline so the user can act on it.

## Decisions

- **Label-only, no section merging** — keep source and untracked sections separate; annotate skills in the source section with a hint. *Rejected: merging into a single line (changes section semantics, ambiguous ownership).*
- **Label text: `(untracked in <providers>)`** — appended after the status, dim styling. Short and actionable. *Rejected: `(has local copy)` (doesn't say which provider); replacing status entirely (loses available/synced info).*
- **Dim color for the hint** — `[dim]` styling so it doesn't compete with status labels. *Rejected: `[cyan]` (visual confusion with status); `[yellow]` (implies warning when it's informational).*
- **Multiple providers comma-separated** — `(untracked in claude, cursor)` on a single line. *Rejected: repeating the skill line per provider (overcomplicates rendering); showing only the first (hides information).*
- **Remove mergeable entries from Untracked section** — once the hint is on the source-section line, showing it again in Untracked is redundant. Untracked section shows only orphans. *Rejected: keeping both (duplicate noise).*
- **Show hints on both available and installed skills** — an untracked copy in another provider is worth surfacing regardless of install status. *Rejected: available-only (misses stray copies in other providers for installed skills).*
- **Build lookup dict upfront in `status()`** — `dict[str, list[str]]` mapping skill name → provider names with untracked copies, built after `_collect_untracked()`, passed to rendering. Clean separation of collection and rendering. *Rejected: computing inside each section renderer (duplicates logic).*

## Open questions

None — all questions resolved during grill.

## Out of scope

- Automatic merging/install of untracked copies (that's `skills install --force`).
- Changes to orphan rendering or classification logic.

## Subtasks

- [x] [s06t0901](s06t0901-build-untracked-lookup-and-pass.md): Build untracked lookup and pass to rendering
- [x] [s06t0902](s06t0902-render-untracked-hint-on-available.md): Render untracked hint on available and installed skills
- [x] [s06t0903](s06t0903-filter-mergeable-entries-from-untracked.md): Filter mergeable entries from Untracked section
