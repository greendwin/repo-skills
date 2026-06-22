---
id: s15t05
slug: grindstory-extract-to-standalone-typescript
status: pending
---

# Grind-story: extract to standalone TypeScript project with a build pipeline

## Context

`grind-story` is the autonomous per-story Workflow (~1327-line single file `.claude/workflows/grind-story.js`) loaded by the Claude Code Workflow runtime as a **bare async function body** (top-level `await`/`return`; `agent`/`parallel`/`pipeline`/`phase`/`log`/`args`/`budget`/`workflow` injected as globals; **no `import`, no filesystem/module access at runtime**). It has grown into a flat pile of pure helpers, ~18 JSON schemas, ~20 prompt builders, and the orchestration loop in one scope. We are refactoring it into a self-contained **TypeScript project** whose build emits that single bare-function-body artifact, and **migrating** the project (plus its stories) out of `repo-skills` into a fresh git repo at `~/grind-story`. The trigger: split phase logic and per-subagent invocation data into real modules, introduce a first-class `Subagent` abstraction, and use real `.ts` source — which a pre-processing build step makes possible and which supersedes the JSDoc-only typing approach planned in s15t04.

This umbrella is authored in repo-skills' tracker for now (the tasker MCP is rooted here); the task subtree migrates onto `~/grind-story/.tasker` as part of the final cleanup slice.

## Decisions

- **Migrate to a fresh repo `~/grind-story`** — fresh `git init` (no history preservation; git-filter-repo unavailable), import the workflow + its `*.test.mjs` + the s15 story dirs, then restructure in place. Already executed: commit `9d4257c "Import grind-story from repo-skills"`. *Rejected: keeping grind-story inside repo-skills (it is becoming a self-contained product, the next-gen dev-loop).*

- **Build output is the runtime artifact** — the build produces `.claude/workflows/grind-story.js` as a bare async function body. *Rejected: shipping hand-written `.js` (the whole point is real modules + types).*

- **Two-tree source layout under `src/`** — phases and per-subagent invocations are the two distinct functional types, kept as sibling subpackages with shared roots:
  ```
  src/
    index.ts        export const meta + default main(); builds ctx+outcomes, drives the pick loop
    subagent.ts     defineSubagent / Subagent<A,R> (name, prompt, schema, label, pure parse, run)
    context.ts      RunContext (frozen immutable config)
    outcomes.ts     Outcomes collector (the ~13 accumulators) + intent-named methods + render(ctx, failure)
    failure.ts      Halt, SkipItem, failConvergence
    domain/         shared TS types: Finding, WorkItem, PickResult, TriageBuckets, ...
    schemas/        shared JSON-schema fragments: FINDING_ITEM, FINDINGS_SCHEMA, PICK_ITEM, ...
    runtime.d.ts    ambient injected globals: agent/parallel/pipeline/phase/log/args/budget/workflow
    invocations/    one module per subagent (~20): branch, bootstrap, roster, pick, implement,
                    lens, triage, review-fix, refactor-lens, refactor-triage, apply,
                    existing-side-tasks, file-side-tasks, verify, fix, reset, reset-to-pending,
                    status, commit
    phases/         one module per phase: setup, bootstrap, pick, implement, review-a, refactor-b,
                    file-side-tasks, verify, status-commit; + helpers.ts (runLensRound, roundTag,
                    phaseCap, the bounded-round loop)
  ```
  *Rejected: co-locating each invocation inside the phase that uses it (several invocations are shared across phases or parameterized — `lens`/`refactor-lens` take a lens+round; `reset`/`reset-to-pending` come from the failure path).*

- **`Subagent<A,R>` abstraction via `defineSubagent`** — each subagent is a single functional instance bundling name, prompt builder, schema, label, a pure `parse`, and `run`. Replaces today's scattered free functions + constants. Each `invocations/*.ts` exports exactly one `Subagent` plus its co-located prompt builder and `parse`.

- **`parse` is the pure, testable raw→typed boundary** — per subagent, `parse(raw: any): R` normalizes the agent's `any` result into a typed shape, collapsing today's scattered guards (`arr(obj,key)`, `(x && x.y) || {}`, `normalizePick`). It is pure (no logging/side effects — over-serve logging etc. moves into `run`), so it is unit-testable in isolation. All subagent-related data lives in that subagent's module.

- **State model: frozen `RunContext` + `Outcomes` collector** — `RunContext` holds immutable config (storyId, packPath, baseRef, maxDepth, totalSideTaskCap, resolved review/refactor lenses, ...). `Outcomes` owns the ~13 mutable accumulators (processed, deferredFindings, delayedFindings, outOfScopeFindings, droppedRefactors, droppedSideTasks, escalations, filedSignatures, filedSideTasks, residualFindings, capSuppressed, sideTaskCount, seen) behind intent-named methods (`deferFinding`, `dropSideTask`, `recordCommit`, `escalate`, ...). `report()` becomes `outcomes.render(ctx, failure)`. Phase signature is `phase(ctx, outcomes, item)`; `index.ts` constructs both and drives the loop. Absorbs s15t0404's "type the accumulators" goal. *Rejected: threading ~13 loose module-level arrays through every phase.*

- **Control-flow primitives in `src/failure.ts`** — the run-spanning loop vocabulary (`Halt`, `SkipItem` sentinel classes; `failConvergence` which builds a `Halt`) lives in its own module, distinct from phase-shared helpers. The loop site uses bare `instanceof Halt` / `instanceof SkipItem`; the old `classifyLoopError`/`loopAction` indirection is **retired**. *Rejected: folding these into `phases/helpers.ts` (they are run-level control flow, not phase logic).*

- **Build pipeline: `tsc --noEmit` + esbuild + post-step** — `tsc --noEmit` is the type authority (catches what esbuild's transpile-only pass ignores); esbuild bundles `src/index.ts`'s import graph into one tree-shaken scope targeting the runtime's node version and strips types; a ~20-line post-step hoists the literal `export const meta = {...}` to the file top (runtime parses it before executing), drops `export`/`export default`, and appends `return await main()` to produce the bare-body shape. Output: `.claude/workflows/grind-story.js`. *Rejected: esbuild alone (no real type checking); the s15t0402 wrapper-based `tsc` over the single file (superseded by a real module build).*

- **Toolchain pinned; tox `js` env gates it** — `package.json` + lockfile under the project root pin exact `typescript`, `esbuild`, `tsx`; a `check-node.py`-style preflight asserts the node version. A tox `js` env runs `tsc --noEmit` + the tests + the build, and **fails if the committed `grind-story.js` is stale** versus a fresh build (artifact-freshness check).

- **Tests: co-located `*.test.ts` importing real modules** — every pure boundary (`parse` per subagent, `Outcomes` methods, `phaseCap`, `roundTag`, `findingSignature`, ...) is directly importable and tested in a `*.test.ts` next to its module, run via `node:test` through `tsx`. The text-slice seam (`_extract-fn.mjs`) and the 6 `*.test.mjs` files are **deleted**, their still-live assertions ported. Production bundle entry is `index.ts`'s graph only, so tests never reach the artifact. *Rejected: a mirrored `test/` tree (co-location keeps the unit→test mapping obvious); a richer runner like vitest (keeps the pinned dependency surface small — tests are plain import + assert, no fixtures/mocking).*

- **Prompt coupling to dev-loop is intentional and stays inline** — `bootstrapPrompt`/`verifyPrompt`/`fixPrompt` keep their repo-skills/dev-loop strings verbatim (`uv run tox`, `docs/agents/task-tracker.md`, `docs/agents/dev-loop.md`, CLAUDE.md conventions), read from the *target* repo at run time. grind-story is the next-generation dev-loop and deliberately inherits dev-loop's runtime contract (used alongside dev-loop as a manual step). *Rejected: genericizing the gate/roster/task-tracker contract into RunContext/args, and even a deferred `target-config.ts` seam — no genericization is wanted.*

## Open questions

- Final task-subtree migration mechanism onto `~/grind-story/.tasker` (on-disk move vs. re-author there) — deferred to the cleanup slice; this umbrella + subtasks are authored in repo-skills' tracker for now.

## Out of scope

- Any change to grind-story's runtime behavior or orchestration semantics — this is a structural extraction + build/tooling change; emitted prompts and schemas stay behavior-preserving.
- Genericizing the dev-loop/target-repo contract (gate command, doc paths, conventions) — intentionally kept coupled.
- Preserving git history from repo-skills during migration (fresh-start import).
- Closing/merging the migrated stories or the `grind/<story-id>` branches.

## Subtasks

- [ ] [s15t0501](s15t0501-build-skeleton-monolith-builds-green.md): Build skeleton: monolith builds green end-to-end
- [ ] [s15t0502](s15t0502-subagent-abstraction-shared-roots-pilot.md): Subagent abstraction + shared roots + pilot invocation
- [ ] [s15t0503](s15t0503-extract-the-remaining-19-invocations.md): Extract the remaining ~19 invocations
- [ ] [s15t0504](s15t0504-state-model-runcontext-outcomes-failurets.md): State model: RunContext + Outcomes + failure.ts
- [ ] [s15t0505](s15t0505-extract-phases-indexts-becomes-the.md): Extract phases; index.ts becomes the thin driver
- [ ] [s15t0506](s15t0506-final-migration-cleanup.md): Final migration cleanup
