---
id: s08t2321
slug: refactor-within-prefix-check-could
status: pending
---

# Refactor: _within prefix check could lean on stdlib is_relative_to with the symlink concern documented at the call site

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "_within prefix check could lean on stdlib is_relative_to with the symlink concern documented at the call site"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/discovery.py:62-70
- severity: nit

The handwritten `parts[:len(root.parts)] == root.parts` reimplements `Path.is_relative_to`, and the docstring's justification (drive-relative / symlinked roots) is already neutralised because both inputs are `.resolve()`d before the comparison in `normalize_repo_dir`. A small private helper duplicating a stdlib method invites readers to wonder what edge case it guards that the stdlib does not. If the resolved-inputs invariant holds, `target.is_relative_to(root)` is equivalent and self-documenting. Routed to delayed (not out-of-scope): no ADR mandates the `.parts` form, so it is not an ADR conflict — but the current code carries a deliberate, documented design decision (chosen specifically to avoid raising across drive-relative/symlinked roots), so reversing it requires reasoning about that invariant and confirming the escaping/absolute tests still hold. That is structural judgement reaching beyond an obvious local collapse, so it is a side-task seed rather than an in-place apply.

## Suggested fix

Inline the check in `normalize_repo_dir` as `if not target.is_relative_to(root): return None` and drop `_within`, or keep `_within` but have it call `path.is_relative_to(root)` and trim the docstring to state only the 'both inputs already resolved' precondition. Confirm the existing escaping/absolute tests still pass.
