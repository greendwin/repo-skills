---
id: s15t0206
slug: sync-task-status-into-the
status: done
---

# Sync task status into the work-item commit

## Goal

Task status lives in git-tracked `.tasker/*.md` frontmatter, so a status transition is a tracked-file modification. The grind-story loop runs `Commit → Status(in-review)`, so the in-review edit lands *after* the commit — left dirty and swept into the *next* work item's commit (or stranded uncommitted at run end for the last work item). Move the in-review transition *before* the commit so the `.tasker` status edit rides in that same work item's commit.

## Decisions & constraints

- **Reorder per work item:** `Implement → … → Verify(green) → Status(in-review) → Commit`. Flip to in-review only after tox is green, but before the commit that records it, so the `.tasker` status edit is staged by `git add -u` into the same commit.
- **Failure semantics (commit fails after in-review set):** accept it — the run hard-fails (depth 0 halt) or discards (side-task `git reset --hard`, which also reverts the status edit back to in-progress). No explicit status rollback; the report already names the halted task and the tree is preserved for inspection.
- **Explicit commit prompt:** tell the commit agent the `.tasker/<…>.md` frontmatter status edits (from the pick and status steps) are *expected* and MUST be included — never unstage or exclude them as noise.
- **Mechanical:** update `meta.description` and `meta.phases` order (`in-review → commit`), and keep `processed.push` after the now-later commit.
