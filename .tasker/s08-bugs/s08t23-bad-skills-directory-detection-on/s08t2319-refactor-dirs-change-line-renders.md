---
id: s08t2319
slug: refactor-dirs-change-line-renders
status: pending
---

# Refactor: `dirs` change line renders a sorted list, hiding active-dir (first-element) ordering

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "`dirs` change line renders a sorted list, hiding active-dir (first-element) ordering"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_source.py:215 + 242 (_change_line) via console.fmt_data:113-114
- severity: minor

`_change_line("dirs", config.skills_dirs, requested.skills_dirs)` routes lists through `fmt_data`, which `sorted()`s them. Since the first skills dir is the semantically significant 'active dir' (merge write-back target per the glossary), printing `a, b` for a stored value of `["b", "a"]` misrepresents which dir became active and makes the change line a lossy view of the data it claims to report. The new multi-dir feature is the first caller to feed an order-significant list into this sorting formatter, so the latent mismatch is now reachable. The fix reaches into the shared `console.fmt_data` helper consumed across many CLI modules (status, provider, update, merge, update-attach), several of which pre-sort their list inputs deliberately; changing the list-branch semantics or adding an `ordered=True` API is order-significant correctness work whose blast radius extends beyond this task's file, so it is routed as a side-task seed rather than applied in place.

## Suggested fix

Render the dirs change line preserving order, e.g. join with `fmt_data` per element without sorting (`", ".join(fmt_data(d) for d in dirs)`) or add an `ordered=True` path to `fmt_data` for list inputs, so the displayed order matches the stored/active ordering. Audit the other list callers of `fmt_data` (`_update_attach.py:150`) when changing the shared helper.
