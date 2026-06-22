---
id: s15t0503
slug: extract-the-remaining-19-invocations
status: pending
---

# Extract the remaining ~19 invocations

## Goal

Move every remaining subagent out of the monolith into its own `invocations/*.ts` module (one `Subagent` instance each), hoisting shared schema fragments to `schemas/` and shared types to `domain/`, with a co-located `*.test.ts` for each `parse` that carries real logic. Build stays green. After this slice the monolith's only remaining responsibility is the phase orchestration + loop.

## Decisions & constraints

- **One module per subagent.** The ~19 remaining: `branch`, `bootstrap`, `roster`, `implement`, `lens`, `triage`, `review-fix`, `refactor-lens`, `refactor-triage`, `apply`, `existing-side-tasks`, `file-side-tasks`, `verify`, `fix`, `reset`, `reset-to-pending`, `status`, `commit`. Each exports exactly one `Subagent` (via `defineSubagent`) plus its co-located prompt builder and pure `parse`.
- **Parameterized agents stay peers.** `lens`/`refactor-lens` take a lens name + round; `triage`/`refactor-triage` are the two triage variants; `reset`/`reset-to-pending` come from the failure path (not one phase). They are normal modules in `invocations/`, not special-cased.
- **Shared schema fragments → `schemas/`.** `FINDING_ITEM` is shared by `lens` + both triages + `apply`; `FINDINGS_SCHEMA`, the triage bucket schemas, etc. land in `schemas/`. Shared domain types (`Finding`, `TriageBuckets`, agent-result shapes) → `domain/`.
- **`parse` purity preserved** for each: collapse the inline guards into a pure `parse`, push any logging into `run`/caller.
- **Prompts relocate verbatim.** Dev-loop/repo-skills coupling (`uv run tox`, `docs/agents/task-tracker.md`, `docs/agents/dev-loop.md`, CLAUDE.md conventions in `bootstrap`/`verify`/`fix` prompts) is **intentional inheritance** and stays inline — no genericization, no `target-config.ts`.
- **Behavior-preserving:** the emitted prompts and schemas for every agent must be unchanged; `index.ts` rewires to call the new Subagents. Build green throughout.

## Edge cases

- `bootstrap`/`verify`/`fix` carry the target-repo contract strings — copy them exactly, do not parameterize.
- The refactor group-apply path (`apply`) has a behavior-preserving group variant (per-member `applied|dropped`) — keep its prompt logic intact.
- `findingSignature` dedupe and the joined-origin (`s08t03+s08t05`) handling for grouped side-tasks live with `file-side-tasks`/`apply` — keep co-located with the right subagent.
- Some agents have trivial/identity `parse` (no logic) — those don't need a `*.test.ts`; only test parses with normalization logic.

## Key files

- `~/grind-story/src/invocations/{branch,bootstrap,roster,implement,lens,triage,review-fix,refactor-lens,refactor-triage,apply,existing-side-tasks,file-side-tasks,verify,fix,reset,reset-to-pending,status,commit}.ts` (new)
- `~/grind-story/src/invocations/*.test.ts` (new — for logic-bearing parses)
- `~/grind-story/src/schemas/*` and `~/grind-story/src/domain/*` (grow — `FINDING_ITEM`, `Finding`, `TriageBuckets`, ...)
- `~/grind-story/src/index.ts` (rewire to use all Subagents)

## Acceptance criteria

- Every subagent invocation in the run is a `Subagent` imported from `invocations/`; no inline prompt/schema/parse constants remain in `index.ts`.
- Shared `FINDING_ITEM` (and other shared fragments) is defined once in `schemas/` and imported by all consumers.
- Each logic-bearing `parse` has a passing co-located `*.test.ts`.
- The built `grind-story.js` emits byte-identical prompts/schemas to before (behavior-preserving).
- `tsc --noEmit` + tox `js` green.
