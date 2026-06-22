---
id: s15t0506
slug: final-migration-cleanup
status: pending
---

# Final migration cleanup

## Goal

Close the migration: remove grind-story's source-of-truth from `repo-skills`, make `~/grind-story` self-tracking, and verify the new repo builds + gates green standalone. After this slice, repo-skills no longer owns grind-story code or its stories, and `~/grind-story` is the single home.

## Decisions & constraints

- **Delete from repo-skills with a pointer.** Remove `.claude/workflows/grind-story.js` (+ `_extract-fn.mjs`, `*.test.mjs`) and the migrated s15 story dirs from `repo-skills`, leaving a short pointer (e.g. a note/README) to `~/grind-story`. Do NOT delete repo-skills' own dev-loop/task-tracker docs — grind-story consumes them from the target repo at run time.
- **Move the `s15t05` task subtree onto `~/grind-story/.tasker`.** Resolve the deferred open question (on-disk move vs. re-author) at execution time; the target repo needs a `docs/agents/task-tracker.md` so its own skills (and `/tdd`) can resolve task-tracker verbs there.
- **`~/grind-story` green standalone:** `tsc --noEmit`, the co-located test suite, the build, and the freshness check all pass in the new repo with no dependency on repo-skills.
- **Behavior parity is the migration bar:** the built `~/grind-story/.claude/workflows/grind-story.js` is behaviorally identical to the original repo-skills workflow.

## Edge cases

- s15t01 (compact-devloop) STAYS in repo-skills — it is not a grind-story story; do not migrate or delete it.
- Don't orphan cross-references: the supersession pointers (added separately to s15t04/s15t0318/0326/0309/0402) point at `s15t05`; if the subtree is physically moved, ensure those pointers still make sense (note the new repo).
- The `grind/<story-id>` branches and the parent s15 story are NOT closed/merged here (out of scope).
- repo-skills' `tox` must stay green after the deletion (no dangling references to the removed workflow/tests).

## Key files

- DELETE from `repo-skills`: `.claude/workflows/grind-story.js`, `_extract-fn.mjs`, `*.test.mjs`; the migrated `.tasker/s15-orchestration/s15t02|03|04|05` dirs (per the move decision)
- ADD to `repo-skills`: a short pointer note to `~/grind-story`
- ADD to `~/grind-story`: `docs/agents/task-tracker.md` (+ the moved task subtree under `.tasker/`)

## Acceptance criteria

- `repo-skills` no longer contains grind-story code/tests; `uv run tox` there is green.
- A pointer to `~/grind-story` exists in repo-skills.
- `~/grind-story` has `docs/agents/task-tracker.md` and the `s15t05` task subtree; its skills can resolve task-tracker verbs locally.
- `~/grind-story`: `tsc --noEmit` + tests + build + freshness check all green standalone.
- The built workflow in `~/grind-story` is behaviorally identical to the original.
