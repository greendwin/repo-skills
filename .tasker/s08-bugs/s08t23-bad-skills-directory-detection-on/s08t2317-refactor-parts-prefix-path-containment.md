---
id: s08t2317
slug: refactor-parts-prefix-path-containment
status: pending
---

# Refactor: parts-prefix path containment logic conceptually overlaps the AMBIGUOUS equality check

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "parts-prefix path containment logic conceptually overlaps the AMBIGUOUS equality check"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/discovery.py:56 and :69
- severity: nit

Both `detect_skills_dir` (`common.parts == git_root.parts`, line 56) and `_within` (`path.parts[:len(root.parts)] == root.parts`, line 69) deliberately reach into `.parts` to get path-flavour-robust comparison rather than using Path.__eq__/is_relative_to. The root-equality test is the boundary case of containment, so the two encode the same parts-comparison decision in two spots. This is largely incidental (distinct semantics: equality vs prefix) and the reviewer explicitly concedes 'leave as-is if the divergent semantics make a shared helper feel forced.' It also collides with the line-56 revert finding (which prefers plain `==` there), so introducing a shared `_same_dir` primitive is speculative structural polish best collected as a side-task seed rather than forced in alongside a conflicting revert.

## Suggested fix

Optionally express the AMBIGUOUS check in terms of a shared primitive, e.g. add `def _same_dir(a, b): return a.parts == b.parts` and reuse it at line 56, keeping `_within` for the prefix case; both then centralize the "compare by parts, not __eq__" decision. Leave as-is if the divergent semantics make a shared helper feel forced.
