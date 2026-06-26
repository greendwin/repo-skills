---
id: s16t31
slug: refactor-current-or-listed-merge
status: pending
---

# Refactor: `_current_or_listed_merge_branches` always lists branches even when the current branch already answers the que

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "`_current_or_listed_merge_branches` always lists branches even when the current branch already answers the query"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:1211 (_current_or_listed_merge_branches), used by _has_merge_branch:1219
- severity: nit

The helper eagerly globs `_list_merge_branches(git)` even when `_has_merge_branch` could short-circuit on a prefixed current branch. The author's own rationale concedes this is not a hot path and that 'accept the cost as negligible and keep the clean tuple shape' is a valid resolution. The combined-tuple shape was the deliberate refactor goal (single home for current-branch precedence); reintroducing a short-circuit in `_has_merge_branch` partially unwinds that consolidation for negligible gain. This is a structural design judgment (consolidation vs. micro-optimization), not an obvious behavior-preserving local win — routed to delayed as a side-task seed.

## Suggested fix

Either accept the cost as negligible and keep the clean tuple shape (preferred — matches the refactor's stated intent), or have `_has_merge_branch` short-circuit: `current = git.current_branch(); return _merge_branch_prefix(current) is not None or bool(_list_merge_branches(git))`, leaving only `_detect_merge_branch` to use the combined helper where both values are genuinely needed.
