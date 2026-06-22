---
id: s15t0401
slug: node-toolchain-tox-js-env
status: pending
---

# Node toolchain + tox js env, replacing the Python bridge

## Goal

`uv run tox` runs a new `js` environment that exercises the existing `.claude/workflows/*.test.mjs` suites directly via node — replacing the Python→node bridge. The `js` env runs, in order: a `check-node.py` preflight → `npm --prefix .claude/workflows ci` → `node --test` over the workflow test files. `tsc` is intentionally NOT wired in this slice (that is Slice 2). This is the tracer bullet: it proves node runs under tox the new way before any type-checking exists.

## Decisions & constraints

- **One direct tox `js` env; delete the Python bridge.** Add a single `js` env to the default `env_list` in `tox.ini`. Delete the four bridge files (`tests/test_workflow_js.py`, `tests/_node_gate.py`, `tests/test_node_gate.py`, `tests/test_tox_js_gate.py`) and remove the `REQUIRE_WORKFLOW_JS_TESTS` `setenv` + `passenv` lines from `[testenv]`. *Rejected: keeping any Python bridge test; a Python REQUIRE_* skip/fail gate (this is the machinery being deleted).*
- **Pin the node toolchain via `package.json` + lockfile under `.claude/workflows/`.** Create `.claude/workflows/package.json` pinning `typescript` and `@types/node` as devDependencies, plus a committed `package-lock.json`. The `js` env runs `npm --prefix .claude/workflows ci` against the lockfile. (This slice only needs `node --test`, but pin the full toolchain now so Slice 2 adds no new deps.) `node_modules/` lives under `.claude/workflows/`. *Rejected: `npx -y typescript@x` on-demand (no lockfile); a global tsc (non-hermetic); a root-level package.json (misrepresents a Python repo).*
- **Node-absent is a hard failure, surfaced via a friendly preflight.** `js` is in the default `env_list`, so `uv run tox` is never green without the JS checks running — matching CLAUDE.md's "all environments" gate. Add a cross-platform `.claude/workflows/check-node.py` (Python is guaranteed present in a tox env) that does `shutil.which("node")` / `shutil.which("npm")` and, on absence, prints an install hint (homepage link + `apt`/`brew`/`nvm` one-liners) and exits non-zero — running BEFORE `npm ci` so the failure has a good signal. The preflight gets NO test (binary present-or-hint check, exercised live every green run). *Rejected: keeping `js` out of env_list (silent coverage blind spot); an inline shell guard (not cross-platform); letting `npm ci` fail raw.*
- The preflight lives under `.claude/workflows/`, NOT `tests/` — it is no longer a pytest, and `pytest testpaths=["tests"]` must not collect it.

## Edge cases

- `npm ci` requires a `package-lock.json`; it errors if absent — generate and commit the lockfile in this slice.
- The `js` env command order matters: preflight first (friendly hint), then `npm ci`, then `node --test`.
- Ensure the deleted `setenv`/`passenv` removal does not strip the `basepython` or other shared `[testenv]` settings.
- `.gitignore` already ignores `.claude/workflows/node_modules/` and `.claude/workflows/*.wrapped.mjs` (added during the design discussion) — confirm node_modules is not staged.

## Key files

- `tox.ini` — add `js` env, add to `env_list`, drop `REQUIRE_WORKFLOW_JS_TESTS` setenv/passenv.
- `.claude/workflows/package.json`, `.claude/workflows/package-lock.json` — new, pin `typescript` + `@types/node`.
- `.claude/workflows/check-node.py` — new preflight.
- Delete: `tests/test_workflow_js.py`, `tests/_node_gate.py`, `tests/test_node_gate.py`, `tests/test_tox_js_gate.py`.
- `.claude/workflows/*.test.mjs` — unchanged; must still pass via the new path.

## Acceptance criteria

- `uv run tox -e js` runs the `.test.mjs` suites via `node --test` and is green when node/npm are present.
- With node/npm absent (simulated), the `js` env fails with the install hint from `check-node.py`, not a raw `npm: command not found`.
- The four bridge Python files no longer exist and `uv run tox` (all envs) is green with `js` in the default `env_list`.
- `REQUIRE_WORKFLOW_JS_TESTS` appears nowhere in `tox.ini`.
