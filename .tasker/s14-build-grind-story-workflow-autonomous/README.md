---
id: s14
slug: build-grind-story-workflow-autonomous
status: pending
---

# Build `grind-story` Workflow — autonomous per-story implement+refactor loop

## Context

We want a deterministic, reusable `Workflow` script (`.claude/workflows/grind-story.js`) that drives a selected story to completion fully autonomously: for each pending subtask it runs a `dev-loop`-style implement→review→refactor cycle, commits the result, and lets a `thermo-nuclear-code-quality-review` pass spawn refactoring side-tasks that the same loop later picks up — until no pending subtasks remain. The motivation for using the `Workflow` tool (not a prose skill) is twofold: the loop is fixed, and we want to avoid a single orchestrator agent whose context grows unbounded. The JS script IS the orchestrator but holds only structured return values; every step is a fresh `agent()` doing one job. We re-encode `dev-loop`'s internals as workflow phases because an `agent()` is a leaf subagent and cannot itself spawn the parallel review/tdd subagents the real skills rely on.

## Decisions

- **Deliverable: a named `Workflow` script** at `.claude/workflows/grind-story.js`, invoked `Workflow({name:'grind-story', args:'<story-id>'})`. *Rejected: a prose skill (can't avoid a growing-context orchestrator); an inline one-off (not reusable/version-controlled).*
- **Topology: one unified pending-queue loop** — each iteration re-list the story subtree, pick the next `pending` subtask (any depth), process it, loop until none remain. Re-querying (not a static JS list) is what absorbs side-tasks created mid-run. *Rejected: strict per-subtask interleave ordering — buys nothing over the queue.*
- **Inner cycle = dev-loop steps 3→4→5 + commit.** Phase A (implement loop): `tdd` → code-review lenses (`general`,`tests`,`performance`) in parallel → triage agent (`fix-now`/`deferred-to-refactor`/`out-of-scope`) → `tdd` fixes; until no `fix-now`, cap 5 rounds. Phase B (refactor loop): lenses `[duplication, thermo-nuclear]` → triage agent (`apply-now`/`delayed`/`out-of-scope`) → `tdd` applies `apply-now` behavior-preservingly; until dry, cap 5. *Rejected: a separate third thermo pass (Phase C) — redundant; thermo already lives in the refactor roster and side-tasks come from triage buckets.*
- **Triage is a structured-output `agent()`, not the JS.** The JS has no judgment, so the bucketing `dev-loop` reserves for "orchestrator only" becomes an `agent()` call returning a validated schema, in every phase.
- **Side-tasks are born from the `delayed` bucket only**, biased aggressively. Triage is instructed: route genuinely valuable structural work (rule-of-three duplication, real code-judo that *deletes* complexity) to `delayed` (→ tracked side-task); reserve `out-of-scope` strictly for ADR-conflicts and noise (reported only, never filed). *Rejected: filing `out-of-scope` as tasks too — would file ADR-violating/pre-existing churn.*
- **Recursion bound: `maxDepth=2` (default) + a hard total-side-task cap backstop.** Side-tasks get the full treatment (implemented, reviewed, in-place-refactored, committed); a subtask already at depth 2 reports its residual thermo findings instead of filing them. The total cap `log()`s when hit. *Rejected: unbounded loop-until-dry — thermo is never fully satisfied, would not converge; depth-1 — user wants "refactor the refactor once more".*
- **Side-tasks are flat children of the story** (siblings of original subtasks), not nested under the spawning subtask. Depth + linkage are baked into the description as a parseable marker, read back each iteration:
  ```
  ## Refactor side-task
  - depth: 1
  - origin: s08t12 — thermo finding "collapse duplicate dispatch branches"
  ```
  Original subtasks have no such section → depth 0. New side-task gets `depth: d+1`. *Rejected: deep hierarchical nesting with depth derived from tree distance — brittle.*
- **Shared context pack, built once per story.** A bootstrap explore agent reads `docs/agents/dev-loop.md` (lens rosters) + `docs/agents/task-tracker.md` (verbs/status roles) + architecture/conventions/ADRs, and writes a pack to a temp path `/tmp/grind-story/<story-id>.md` (outside the working tree). Every downstream agent gets the path + a "Read this first" instruction. Currency is per-iteration via each agent inspecting the current `git diff` against the branch base ref — no per-subtask re-exploration, pack not rebuilt for side-tasks. *Rejected: rebuild per subtask (burns the savings); write inside repo (risks being committed, muddies the diff).*
- **Source lenses & task-tracker verbs from repo config at runtime**, never hardcoded — the bootstrap agent folds the resolved prose into the pack; review/triage/status agents use it. Preserves the single source of truth the whole skill family depends on. *Rejected: hardcoding lens prompts/MCP calls in JS — drifts from configs.*
- **Runs on a dedicated `grind/<story-id>` branch** created from current HEAD at start; all commits land there; the branch point is also the base ref for the live-diff freshness signal. *Rejected: committing on the current branch (risky for unattended grind); full git worktree (unneeded — loop is sequential, only one `tdd` writes at a time).*
- **Fully autonomous — no human gates.** The mandatory gates in `dev-loop`/`to-tasks`/`todo-triage` (planning approval, side-task approval, commit confirmation) are dropped because a background workflow can't do mid-run `AskUserQuestion`. Safety comes from the caps, the green-test contract on every commit, subtasks ending `in-review` (never auto-`done`), and a thorough final report; the user's review moment moves from "during" to "after".
- **Green gate before every commit.** A verify agent runs `uv run tox` (all envs); red → route failures to a `tdd` fix agent and re-run, bounded by the same 5-round cap. Every commit is full-`tox`-green, honoring `CLAUDE.md` (incl. the "fix pre-existing" rule). `tdd`'s own contract (targeted tests) is insufficient on its own.
- **One commit per subtask via a commit agent** running `commit-summary`'s message logic. Staging is non-interactive: `git add -u` + the source/test files `tdd` created, skipping (never prompting on) denylisted/suspicious untracked files and `log()`ing skips. No task-id in the commit message (matches repo log style); the task→commit-sha→origin linkage lives in the final report.
- **Status transitions:** pick subtask → `in-progress` (`start_task`); cycle converges + commits → `in-review` (`review_task`); never auto-`done`. Side-tasks born `pending` via `create_subtask`. The parent story is never transitioned — the user closes it.
- **Failure semantics (kind-split, mirrors dev-loop's green contract):** an *original* subtask that can't converge (tdd never green / `fix-now` open at cap / `tox` red at cap) → **halt the run**, leave the working tree dirty for inspection, prior commits preserved, report the failure point. A *side-task* (depth ≥ 1) that can't converge → `git reset --hard` to discard its uncommitted changes (clean base, since the prior subtask is committed), mark it dropped, **continue** with the next pending subtask.
- **Final report:** task→commit-sha→origin map, dropped side-tasks, out-of-scope findings, escalations.

## Open questions

- Total-side-task backstop cap value — default to a sane number (e.g. ~30) and `log()` when hit; tune later. Deferred.
- Per-agent model/effort overrides (e.g. higher effort for thermo/triage) — inherit session defaults unless a need shows up. Deferred.

## Out of scope

- A prose-skill variant of this orchestration — explicitly rejected in favor of the deterministic `Workflow`.
- Interactive/mid-run approval gates — incompatible with a background workflow.
- Editing `docs/agents/dev-loop.md` or `task-tracker.md` rosters/verbs — this workflow consumes them, doesn't change them.
- Auto-merging the `grind/<story-id>` branch or closing the story — left to the user.

## Subtasks

- [x] [s14t01](s14t01-tracer-bullet-skeleton-grind-story.md): Tracer bullet: skeleton grind-story loop end-to-end
- [x] [s14t02](s14t02-phase-a-implement-review-loop.md): Phase A: implement review loop with triage and fix-reconverge
- [x] [s14t03](s14t03-phase-b-refactor-loop-with.md): Phase B: refactor loop with duplication and thermo-nuclear lenses
- [x] [s14t04](s14t04-side-task-filing-from-delayed.md): Side-task filing from `delayed` and depth-bounded re-queue
- [ ] [s14t05](s14t05-failure-semantics-and-full-run.md): Failure semantics and full run report
