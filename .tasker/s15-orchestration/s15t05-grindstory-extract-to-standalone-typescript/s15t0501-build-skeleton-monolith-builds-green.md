---
id: s15t0501
slug: build-skeleton-monolith-builds-green
status: pending
---

# Build skeleton: monolith builds green end-to-end

## Goal

Stand up the TypeScript project + build pipeline in `~/grind-story` so that `src/index.ts` builds into `.claude/workflows/grind-story.js` (a bare async function body) and a tox `js` env runs green — with the workflow body still **monolithic** (whole current code inside `default main()`). This is the tracer bullet: it proves the body-shape transform and the freshness gate before any module decomposition.

## Decisions & constraints

- **Build output is the runtime artifact.** The Workflow runtime loads `.claude/workflows/grind-story.js` as a bare async function body — top-level `await`/`return`, with `agent`/`parallel`/`pipeline`/`phase`/`log`/`args`/`budget`/`workflow` injected as globals; **no `import`, no FS at runtime**. The build must emit exactly that shape.
- **Pipeline = `tsc --noEmit` + esbuild + post-step.** `tsc --noEmit` is the type authority (esbuild only transpiles, doesn't type-check). esbuild bundles `src/index.ts`'s import graph into one tree-shaken scope, targets the runtime node version, strips types. A ~20-line post-step hoists the literal `export const meta = {...}` to file top (the runtime parses meta before executing), drops `export`/`export default` keywords, and appends `return await main()`. *Rejected: esbuild alone (no real typecheck); s15t0402's wrapper-based tsc over the single file (superseded).*
- **Toolchain pinned.** `package.json` + committed lockfile under the project root pin exact `typescript`, `esbuild`, `tsx`. A `check-node.py`-style preflight (Python is guaranteed present) does `shutil.which("node")` and exits non-zero with an install hint if absent.
- **tox `js` env** runs, in order: node preflight → install from lockfile → `tsc --noEmit` → (tests, lands in later slices) → build → **artifact-freshness check** that fails if the committed `grind-story.js` differs from a fresh build. Replaces the Python→node bridge described in s15t04.
- **`runtime.d.ts`** declares the injected globals as ambient (resolves what would otherwise be undeclared-global type errors) and doubles as living documentation of the Workflow API.
- **Monolith stays behavior-preserving.** `src/index.ts` initially holds the entire current workflow body verbatim as `export default async function main() { ...current body... }` plus the hoisted `export const meta`. No logic changes; the emitted `grind-story.js` must be behaviorally identical to today's file.

## Edge cases

- The current file's tail is already `return report(...)`; inside `main()` that's a normal function return — the post-step's appended `return await main()` is the only top-level return.
- `export const meta` must be a pure literal at file top in the output (runtime parses it statically) — the post-step hoists it above everything.
- esbuild target must match the runtime's node version (don't down-level top-level constructs the runtime supports, don't emit syntax it doesn't).
- Freshness check must compare normalized output (e.g. exact bytes of a fresh build) so a stale commit fails CI.

## Key files

- `~/grind-story/src/index.ts` (new — monolith body + meta)
- `~/grind-story/src/runtime.d.ts` (new — ambient globals)
- `~/grind-story/package.json` + lockfile, `tsconfig.json` (new)
- build script + ~20-line post-step (new)
- `~/grind-story/check-node.py` preflight (new)
- `~/grind-story/tox.ini` (new/adapted — `js` env)
- `~/grind-story/.claude/workflows/grind-story.js` (now a build artifact)

## Acceptance criteria

- `npm run build` (or equivalent) produces `.claude/workflows/grind-story.js` as a bare function body starting with `export const meta`-derived literal at top and ending with `return await main()`.
- `tsc --noEmit` passes over `src/`.
- The tox `js` env runs green: preflight → typecheck → build → freshness check.
- Re-running the build is idempotent (no diff); deliberately editing the committed artifact makes the freshness check fail.
- The built workflow is behaviorally identical to the pre-refactor `grind-story.js` (same meta, same emitted logic).
