---
id: s15t04
slug: grindstory-typecheck-the-workflow-with
status: pending
---

# [SUPERSEDED→s15t05] Grind-story: type-check via JSDoc+tsc (obsolete: real TS build supersedes; toolchain/typing survivors absorbed into s15t05)

## Context

`grind-story` is the autonomous per-story Workflow at `.claude/workflows/grind-story.js` (~1300 lines). It is loaded by the Claude Code Workflow runtime as a **bare function body** (top-level `return`, top-level `await`, with `agent`/`parallel`/`pipeline`/`phase`/`log`/`args`/`budget`/`workflow` injected as globals). We want type safety over its pure helpers and domain contracts. Literal `.ts` is impossible — the runtime rejects type annotations and the function-body form is not a valid TS module. So the rework is: keep the file plain JS, add `// @ts-check` + JSDoc, and verify with `tsc --noEmit --checkJs` over a *wrapped* form. At the same time, replace the existing Python→node test bridge (which shells `node --test` and polices a `REQUIRE_WORKFLOW_JS_TESTS` skip/fail gate) with a dedicated tox `js` env that invokes the node toolchain directly.

## Decisions

- **Type via JSDoc + `@ts-check`, not literal `.ts`** — the Workflow runtime `eval`s the file as a function body and rejects type annotations; shipping `.ts` is off the table. Keep `grind-story.js` plain JS, annotate with JSDoc, verify with `tsc --noEmit --checkJs`. *Rejected: authoring `.ts` and compiling to a committed `.js` (adds a build step, tsconfig, and a compiled-artifact-drift hazard in a repo with no package.json); typing only the test seam (leaves the workflow body unchecked).*

- **One direct tox `js` env; delete the Python bridge** — add a single `js` env to the default `env_list` running, in order: a node preflight → `npm --prefix .claude/workflows ci` → `tsc -p .claude/workflows` (fail fast) → `node --test`. Remove `test_workflow_js.py`, `_node_gate.py`, `test_node_gate.py`, `test_tox_js_gate.py`, and the `REQUIRE_WORKFLOW_JS_TESTS` `setenv`/`passenv` in `tox.ini`. *Rejected: keeping a Python bridge test (Q2); a Python `REQUIRE_*` skip/fail gate (machinery being deleted); two separate envs for tsc vs node --test — both share one `npm ci`, so splitting only doubles install cost.*

- **Pin the node toolchain via `package.json` + lockfile under `.claude/workflows/`** — `typescript` and `@types/node` pinned; `npm --prefix .claude/workflows ci` against a committed `package-lock.json` is the only reproducible option. Manifest, lockfile, and `node_modules/` all live under `.claude/workflows/` (the only dir using node), keeping the Python root honest. *Rejected: `npx -y typescript@x` on-demand (network fetch, no lockfile); a global `tsc` (non-hermetic, drifts per machine); a root-level package.json (misrepresents a Python repo as an npm project).*

- **Node-absent is a hard failure, surfaced via a friendly preflight** — `js` is in the default `env_list`, so `uv run tox` is never green without the JS checks actually running (matches CLAUDE.md's "all environments" gate and the repo's existing opt-in posture). A cross-platform `check-node.py` preflight (Python is guaranteed present in the env) does `shutil.which("node"/"npm")` and, on absence, prints an install hint and exits non-zero before `npm ci` runs raw. *Rejected: keeping `js` out of the default env_list (recreates the silent coverage blind spot the deleted gate fought); an inline shell guard (not cross-platform); letting `npm ci` fail raw (poor signal). The preflight gets no test — it collapses to a binary present-or-hint check the `js` env exercises every green run.*

- **Make the function-body file checkable via a generated wrapper** — `tsc` rejects the raw file (empirically: TS1375 top-level await needs a module, TS1108 top-level return illegal, TS2304 undeclared globals), and its suggested fixes (`export {}`) would break the runtime; there is no global per-error-code suppression. So a small `check-types.mjs` reads `grind-story.js`, wraps its content as `export async function __wf(){ <body> }` into a gitignored `*.wrapped.mjs` (wrapper prefix on line 1 to keep reported line numbers aligned), then runs `tsc -p`. The shipped file stays byte-for-byte a bare function body. *Rejected: restructuring into an `async function main()` ending `return await main()` (that final line is still top-level return+await); checking only pure helpers extracted to a sidecar module (the runtime loads one self-contained body and cannot import).*

- **Committed `globals.d.ts` declares the injected runtime API** — ambient declarations for `agent`, `parallel`, `pipeline`, `phase`, `log`, `args`, `budget`, `workflow`, resolving TS2304 and doubling as living documentation of the Workflow API surface. Scoped to the runtime API only.

- **Committed `tsconfig.json`, `strict: true`, excluding the raw file** — `allowJs`, `checkJs`, `noEmit`, es2022 target/module (top-level await in the wrapper), `types: ["node"]`. It **excludes** the raw `grind-story.js` (would re-hit TS1108) and includes `globals.d.ts`, the generated `*.wrapped.mjs`, and the node-typed test files. Mirrors the repo's `mypy strict` posture, drives editor IntelliSense, and keeps `check-types.mjs` to "generate wrapper, call `tsc -p`." *Rejected: pure CLI flags (long, awkward raw-file exclusion, no in-IDE checking).*

- **`tsc` checks the whole `.claude/workflows/` JS surface** — the wrapped `grind-story.js`, all `*.test.mjs`, `_extract-fn.mjs`, and `check-types.mjs`, requiring a pinned `@types/node`. The tests are the highest-value thing to keep aligned with the helper signatures. *Rejected: checking only the wrapped workflow (leaves the tests — most likely to drift against the extracted helpers — unchecked).*

- **Domain typedefs inline in `grind-story.js`, beside their `*_SCHEMA`** — `Finding`, `PickItem`, the `{done, kind, items}` pick, the triage buckets, and the agent-result shapes are JSDoc `@typedef`s co-located with the matching schema literals (they travel with the body into the wrapper; the function body can't `import` anyway). `globals.d.ts` stays runtime-API-only. *Rejected: a separate `.d.ts` sidecar (the body can't import them so they'd be ambient global types that drift from their schema literals).*

- **Type the pure helpers + accumulators fully; leave agent results `any`** — `agent()` returns `Promise<any>` by runtime contract. Fully type the pure helpers (`normalizePick`, `parseDepthMarker`, `buildSideTaskDescription`, `findingSignature`, `phaseCap`, `firstRepeat`, `recordSeen`) and the module-level accumulator arrays (`deferredFindings`, `droppedSideTasks`, `escalations`, …) so every `.push` is shape-checked; cast only the pick result into `normalizePick`; let other `agent()` results stay `any`. The helpers hold the logic that can actually be wrong. *Rejected: full casts at every ~20 agent call sites — ceremony around `any`-by-contract data that tsc can't meaningfully verify.*

## Open questions

- None outstanding from the grill.

## Out of scope

- Any change to grind-story's runtime behavior or orchestration logic — this is typing + test-tooling only.
- Converting any other skill/workflow to TS (grind-story.js is the only workflow file).
- A literal `.ts` source or any build/compile step that changes what the runtime loads.
- Updating docs/README for the bridge removal (no references exist).

## Subtasks

- [ ] [s15t0401](s15t0401-node-toolchain-tox-js-env.md): Node toolchain + tox js env, replacing the Python bridge
- [ ] [s15t0402](s15t0402-wrapperbased-tsc-check-wired-in.md): [SUPERSEDED→s15t05] Wrapper-based tsc check (obsolete: replaced by real TS build)
- [ ] [s15t0403](s15t0403-type-the-pure-helpers-domain.md): Type the pure helpers + domain typedefs under @ts-check
- [ ] [s15t0404](s15t0404-type-the-orchestration-accumulators-pickresult.md): Type the orchestration accumulators + pick-result cast
