---
id: s06t18
slug: update-specific-source
status: pending
---

# Update specific source

## Context

`skills update` pulls *every* registered source then updates all-or-one skill. Users want to scope an update to a single source (`-s/--source agent-skills`) and, more generally, a clean filter model that future filters can extend. This task reshapes `update` into a unified collection model and is the seam that s06t16 (auto-attach) plugs into.

Implementation order: **t18 → t16 → t19**.

## Decisions

- **Unified collection model** — `update` becomes *collect target skills → derive sources to pull → process*. Filters compose: no args = all installed; positional `name` = one skill; `-s/--source` = skills from that source; future filters slot into the same collection step. *Rejected: bolting `-s` on as a special case beside the existing all/one-skill branches — doesn't generalize.*
- **`-s` and `name` compose** — both apply as filters; a named skill not belonging to the given source → clear error. *Rejected: mutually-exclusive flags; silent precedence of one over the other.*
- **Pulls derived from the collected set** — pull only sources owning ≥1 target skill. Consequence: a registered source with zero installed skills is never pulled, even on no-arg `update` (accepted behavior change / efficiency fix). *Rejected: keep pulling all registered sources up front.*
- **Error semantics** — unknown `-s` source → `AppError` "Source X not found" (reuse the registry's existing not-found error); valid source with no target skills → `NoopError`, but the empty check must run *after* attach-candidates are considered (see s06t16) so it can't wrongly no-op once t16 lands.
- **`-s/--source` short+long option** — mirror the existing `install`/`merge` spelling (`"--source", "-s"`).

## Open questions

- None.

## Out of scope

- The attach mechanism itself (s06t16) — t18 only builds the collection seam and must leave the post-collection empty-check positioned so attach-candidates can extend it.
- Other future filters (only the composable seam is built, not new filters).
- Changing the name-only / no-arg pull behavior beyond what the derived-pull model implies.

## Subtasks

- [ ] [s06t1801](s06t1801-extract-targetskill-collection-as-a.md): Extract target-skill collection as a seam
- [ ] [s06t1802](s06t1802-ssource-filters-the-update-work.md): `-s/--source` filters the update work set
- [ ] [s06t1803](s06t1803-derive-pulls-from-the-collected.md): Derive pulls from the collected skill set
