---
id: s06t13
slug: allow-to-omit-skill-name
status: pending
---

# Allow to omit skill name when only one skill is modified

## Context

When `skills merge` is run with no skill name, it currently fails with "Skill name is required." In the common case there is exactly one obvious thing to merge (e.g. a single `modified` skill), so the user should be able to omit the name and have it auto-detected. The goal is a zero-argument convenience flow that picks the pending skill, while keeping all existing safety guards (provider ambiguity, in-progress merges) intact.

## Decisions

- **Layered cascade for detection** — scan candidate buckets in precedence order `modified` -> `mergeable` -> `orphan`. The first non-empty layer decides: exactly one candidate -> pick it; more than one -> error and stop (no fall-through to the next layer); zero -> fall through to the next layer. Matches the task's "only one skill is modified" wording while still helping when only mergeable/orphan work is pending.
- **Count distinct skill names, not (skill, provider) pairs** — a skill modified under two providers is one candidate. Auto-detect resolves only the skill *name*; provider resolution stays a separate downstream step. Avoids spurious "ambiguous" errors when there is really one skill. *Rejected: counting (skill, provider) pairs (would falsely report ambiguity).*
- **Provider resolution behavior unchanged** — if the auto-detected skill is modified in multiple providers and no `--from` is given, the existing `_resolve_diverged_provider` "use --from" error still fires. *Rejected: silently picking the first provider (would discard one provider's edits without warning).*
- **`--from`/`--source` narrow the candidate scan** — when given, they filter which candidates the layers consider (e.g. `--from claude` only counts skills pending under claude). Honors user intent and reduces spurious ambiguity. *Rejected: pass-through only, always scanning all providers/sources.*
- **Error wording** — ambiguous layer raises `AppError` listing candidates, e.g. `Multiple modified skills (grill-me, to-tasks). Specify which to merge.` with hint `Run skills merge <skill> to choose.` (substituting the tripped layer's name). All layers empty raises `NoopError`: `Nothing to merge — no modified, mergeable, or orphan skills found.` Reuses the file's existing `AppError`/`NoopError` patterns.
- **Short-circuit on in-progress merge** — before scanning layers, if any source repo has a `skill-merge/...` branch, error with the `--continue`/`--abort` nudge (preserving the spirit of the old "Skill name is required" hint). Reuse `_has_merge_branch`. Prevents starting a second, unrelated merge while one is half-finished.
- **Announce the auto-detected pick** — print a one-line notice before proceeding, e.g. `Auto-detected modified skill grill-me.` (via `fmt_ident`). Auto-selection triggers repo-mutating work, so surface the decision.
- **Mirror `status` classification exactly** — auto-detect's `modified`/`mergeable`/`orphan` layers share one classification function with the `status` command, so the two never disagree. In particular a *detached* skill lands in `mergeable`/`orphan`, never `modified` (matching how `status` presents it). Requires factoring classification out of `_status.py` into shared logic.

## Open questions

- None outstanding.

## Out of scope

- Changing provider disambiguation behavior (`--from` resolution stays as-is).
- Auto-detect for the explicit-skill-name path (it already has a name).
- Any change to `--continue`/`--abort` mechanics beyond the up-front short-circuit.

## Subtasks

- [ ] [s06t1301](s06t1301-extract-shared-skillclassification-module.md): Extract shared skill-classification module
- [ ] [s06t1302](s06t1302-layered-autodetect-wired-into-merge.md): Layered auto-detect wired into merge
- [ ] [s06t1303](s06t1303-guards-and-error-wording.md): Guards and error wording
