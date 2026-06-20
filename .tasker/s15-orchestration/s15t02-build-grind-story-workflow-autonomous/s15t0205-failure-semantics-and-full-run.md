---
id: s15t0205
slug: failure-semantics-and-full-run
status: done
---

# Failure semantics and full run report

## Goal

Add kind-split failure handling so an unattended run is resilient to a bad refactor idea but still stops hard when real feature work breaks, and produce the post-hoc report that replaces the dropped human gates.

## Decisions & constraints

- **Kind-split failure handling** (mirrors `dev-loop`'s green contract — feature-can't-go-green escalates, refactor-can't-stay-green is dropped):
  - **Original subtask** (depth 0) that can't converge — `tdd` never reaches green, `fix-now` still open at the 5-round cap, or `tox` red at the cap → **halt the entire run**. Leave the working tree dirty for inspection; prior subtask commits are preserved on the branch; report names the failure point and reason.
  - **Side-task** (depth ≥ 1) that can't converge → **`git reset --hard`** (via an agent) to discard just that side-task's uncommitted changes — the tree is clean because the prior subtask is already committed — mark it dropped in the report, and **continue** with the next pending subtask.
- **Prior commits are always preserved** regardless of failure path.
- **Final report** (returned by the workflow / surfaced to the user) contains:
  - task → commit-sha → origin map (every committed subtask, with its origin marker if a side-task),
  - dropped side-tasks (with reason),
  - out-of-scope findings collected across subtasks (recorded, not filed),
  - escalations (the halting original subtask, any 5-cap-open `fix-now`, residual depth-2 thermo findings, cap-suppressed side-tasks).
- The report is the review surface that replaces the autonomous run's missing interactive gates; nothing is auto-`done`, so the user reviews the branch + report and closes the story themselves.

## Edge cases

- Halt occurs after some subtasks already committed → those commits stay on the branch; report reflects partial completion clearly.
- `git reset --hard` on a side-task must not touch the context-pack temp file (it's outside the tree) or prior commits.
- Multiple side-tasks dropped across the run → all listed in the report with reasons.
- Run completes with zero failures → report still lists every commit, out-of-scope findings, and any residual/suppressed items.

## Key files

- `.claude/workflows/grind-story.js` — wrap the per-subtask cycle with kind-split failure handling and assemble/return the final report.

## Acceptance criteria

- An original subtask that cannot reach green halts the run with a dirty tree, preserved prior commits, and a report naming the failure.
- A side-task that cannot reach green is `git reset --hard`-discarded and the loop continues with the next pending subtask.
- The final report contains the full task→commit-sha→origin map, dropped side-tasks with reasons, recorded out-of-scope findings, and all escalations.
- A clean full run reports every commit and terminates with no `pending` subtasks left and nothing auto-`done`.
