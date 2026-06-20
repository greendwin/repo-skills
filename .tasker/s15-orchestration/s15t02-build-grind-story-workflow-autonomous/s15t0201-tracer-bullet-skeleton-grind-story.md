---
id: s15t0201
slug: tracer-bullet-skeleton-grind-story
status: done
---

# Tracer bullet: skeleton grind-story loop end-to-end

## Goal

A runnable `Workflow` script at `.claude/workflows/grind-story.js`, invoked `Workflow({name:'grind-story', args:'<story-id>'})`, that drives one trivial pending subtask end-to-end: create branch → bootstrap context pack → pick subtask → implement → tox-gate → commit → status, then emit a minimal report. No reviews/refactor/side-tasks yet — this proves the full deterministic wiring.

## Decisions & constraints

- **Named `Workflow` script, not a prose skill.** The JS is the orchestrator but holds only structured return values; every step is a fresh `agent()`. We re-encode skill internals as phases because an `agent()` is a leaf subagent and cannot spawn its own sub-agents.
- **Branch:** create `grind/<story-id>` from current HEAD at start (an agent runs the git commands — the JS has no shell). This branch point is the base ref for the live `git diff` freshness signal used by later agents.
- **Bootstrap (once per run):** an explore agent reads `docs/agents/dev-loop.md` (lens rosters) + `docs/agents/task-tracker.md` (verbs + status roles) + architecture/conventions/ADRs/glossary (`CLAUDE.md`, `CONTEXT.md`) and writes a context pack to `/tmp/grind-story/<story-id>.md` (outside the working tree, so it's never committed and never pollutes the diff). It returns the path + a short digest. Every downstream agent prompt carries the path + "Read this first".
- **Source config at runtime, never hardcode** rosters/verbs/status-roles — fold the resolved prose into the pack.
- **Queue loop:** each iteration, re-list the story subtree via the `list-tasks`/`read-task` verbs and pick the next `pending` subtask. Degenerate case: a story with no subtasks → treat the story task itself as the single work item. Terminate when no `pending` remain.
- **Per subtask:** `set-status` → `in-progress`; one `tdd` implement agent (told plan is pre-approved, skip-review path, return green; passed the pack path + task id); a verify agent runs `uv run tox` (all envs) and on red routes failures to a `tdd` fix agent, re-running, bounded by a 5-round cap; a commit agent composes the message via `commit-summary` logic and commits (staging: `git add -u` + tdd-created source/test files, skipping/never-prompting denylisted/suspicious untracked, `log()`ing skips; no task-id in message); `set-status` → `in-review` (never auto-`done`).
- **Fully autonomous** — no interactive gates anywhere.
- **`meta` block** must be a pure literal with `name`, `description`, and a `phases` array.

## Edge cases

- Story has zero subtasks → process the story task itself.
- `uv run tox` red on the very first subtask (incl. pre-existing failures) → fix-loop then, if still red at cap, this is a hard failure (full handling lands in Slice 5; here it's acceptable to `log()` + stop).
- Untracked files that look like secrets/artifacts → skipped, never staged, never prompted.
- Context-pack temp dir may not exist → the explore agent creates `/tmp/grind-story/` before writing.

## Key files

- `.claude/workflows/grind-story.js` (new) — the entire deliverable.
- `.claude/workflows/` (new dir).
- Consumed read-only at runtime: `docs/agents/dev-loop.md`, `docs/agents/task-tracker.md`, `CLAUDE.md`, `CONTEXT.md`.
- Precedent for local tooling style: `.claude/skills/prepare-release/SKILL.md`.

## Acceptance criteria

- Invoking the workflow on a story with a single trivial pending subtask: creates `grind/<story-id>`, writes `/tmp/grind-story/<story-id>.md`, transitions the subtask `pending`→`in-progress`→`in-review`, produces exactly one commit on the branch with a `commit-summary`-style message, leaves `tox` green, and prints a report naming the subtask and its commit sha.
- The script's `meta` is a pure literal; phase titles in `meta.phases` match the `phase()` calls.
- No task id appears in the commit message; no human prompt occurs during the run.
- A story with no subtasks processes the story task itself.
