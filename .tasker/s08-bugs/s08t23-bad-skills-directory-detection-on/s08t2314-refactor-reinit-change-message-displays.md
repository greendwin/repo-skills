---
id: s08t2314
slug: refactor-reinit-change-message-displays
status: pending
---

# Refactor: Reinit change message displays skills_dirs sorted, hiding the active-dir order

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "Reinit change message displays skills_dirs sorted, hiding the active-dir order"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_source.py:215-217 (_handle_reinit)
- severity: minor

The dirs-change line is built with fmt_data(config.skills_dirs) and fmt_data(requested.skills_dirs); fmt_data sorts list values alphabetically (console.py:114). The list order is semantically load-bearing: the FIRST dir is the active/merge-target dir (ADR-0005, SourceConfig.active_dir). For `--skills-dir b --skills-dir a` the stored list is ["b","a"] (b is active) but the change message prints `dirs: ... -> a, b`, misrepresenting which dir becomes active. The equality comparison itself is order-sensitive and correct; only the human-facing message is misleading. The fix requires changing the shared fmt_data list-sorting behaviour or adding an order-preserving formatter used by other call sites, so it reaches beyond this slice and is routed to delayed.

## Suggested fix

Render the dirs in stored order rather than via fmt_data's list-sort, e.g. join explicitly preserving order: `new_dirs = ', '.join(fmt_data(d) for d in requested.skills_dirs)` (and likewise for old_dirs), or add an order-preserving fmt helper. The spec only mandates using fmt_data, so an order-preserving formatter still satisfies it.
