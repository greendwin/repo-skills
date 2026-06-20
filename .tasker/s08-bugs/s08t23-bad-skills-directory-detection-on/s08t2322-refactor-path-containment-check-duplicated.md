---
id: s08t2322
slug: refactor-path-containment-check-duplicated
status: in-review
---

# Refactor: Path-containment check duplicated between new _within helper and _merge.py

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "Path-containment check duplicated between new _within helper and _merge.py"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_merge.py:769 (vs src/repo_skills/discovery.py:62 _within)
- severity: minor

The diff introduces discovery._within(path, root) to express "path is root itself or nested inside it". _merge.py:769 expresses the identical concept inline as `cwd == source.repo_root or source.repo_root in cwd.parents`. This is true (not incidental) duplication of a single domain notion — repo containment. Now that a named, documented helper for it exists, the inline copy is a second source of truth: a future hardening of containment semantics (e.g. the .resolve()/parts robustness the docstring describes for Windows drive-relative or symlinked roots, exactly the class of bug ADR-0004 warns about) would have to be applied in two places, and the inline `in .parents` form is precisely the form the helper's docstring says it deliberately avoids.

## Suggested fix

Promote _within to a public, intent-named containment predicate (e.g. `path_within(path, root)`/`is_within_repo`) in discovery.py, resolving both inputs internally so callers need not pre-resolve, and have _merge.py's selection loop call it: `if path_within(cwd, source.repo_root): return git`. normalize_repo_dir keeps using it as today. If cross-module reuse is judged premature, at minimum drop a comment at _merge.py:769 pointing to _within so the duplication is tracked.
