---
id: s15t0304
slug: one-pass-group-execution-apply
status: cancelled
---

# One-pass group execution: apply + single commit

## Goal

A refactor group runs one behavior-preserving group-apply, then the full pipeline (Review-A → Refactor-B → file-side-tasks → Verify) over the combined diff, then **one** commit; each member gets its own `processed` row sharing that commit sha.

## Decisions & constraints

- **Group apply prompt**: a group-aware variant of Refactor-B's `applyPrompt` — apply all N refactorings keeping existing tests green, never write new behavior tests, return per-member results `{member-id/title, outcome: applied|dropped, reason}`. A member that can't stay green is dropped (reason recorded), never forced. (Drop→cancel handling lands in Slice 5; this slice must surface the per-member applied/dropped results.)
- **Full pipeline for refactor groups**: after apply, run Review-A, Refactor-B, file-side-tasks, and Verify once over the combined diff, then commit. `maxDepth` bounds refactor-of-refactor recursion; Review-A remains the correctness safety net.
- **Side-task attribution for groups** (`fileSideTasks` / `buildSideTaskDescription` / `findingSignature`): use `min(member depths)` for both the depth-suppression gate and the filed child's birth depth (more permissive within `maxDepth`). The child's `origin:` line lists **all** member ids joined (e.g. `s08t03+s08t05`); that joined string is the `originTaskId` fed to `findingSignature`, since a combined-diff finding can't be pinned to one member.
- **Single commit**: the group commit stages all members' `.tasker` in-review edits and source/test changes; message summarizes the batched refactors with **no task ids** (per CLAUDE.md). Status step moves every member to in-review before the commit.
- **Report**: push one `processed` row per member, all sharing the single commit sha, each tagged with its own origin/provenance.
- Feature picks (group of one) keep today's exact single-task behavior — this generalization must not change feature-task processing.

## Edge cases

- Mixed-depth members: min-depth governs the gate/birth depth; verify a depth-2 + depth-1 group files children at min+1.
- Some members applied, some dropped (none causing hard failure): the group still proceeds with the applied subset (cancellation of dropped members is Slice 5).
- All members applied cleanly: one commit, N processed rows.

## Key files

- `.claude/workflows/grind-story.js` — new group-apply prompt (modeled on `applyPrompt`/`APPLY_SCHEMA`), `implement`/loop-body wiring, `reviewPhaseA`/`refactorPhaseB`/`fileSideTasks` to accept a group + min-depth, `buildSideTaskDescription`/`findingSignature` origin handling, `statusAndCommit`/`commitPrompt`/`statusPrompt` for N members, `processed` rows in `report`.

## Acceptance criteria

- A multi-member refactor group applies via one group-apply agent and produces exactly one commit covering all applied members.
- Side-tasks filed from the group are born at `min(member depths)+1` and their `origin:` line lists the joined member ids.
- Every member is moved to in-review and appears as its own `processed` row sharing the commit sha.
- Feature-task (group-of-one) processing is unchanged.
- `uv run tox` (all envs) green.
