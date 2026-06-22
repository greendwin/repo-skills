---
id: s08t2324
slug: dedup-two-source-test-fixture
status: in-review
---

# Dedup two-source test fixture into a helper

## Goal

Several orphan/untracked merge tests repeat the same two-source setup ritual: create `other_repo` with a `.git` dir, build a `SourceRegistry`, register both sources, `save_source_registry`, then two `save_source_config(SourceConfig(..., skills_dirs=["skills"]))` calls. Extract a shared helper to remove this duplication.

## Findings origin

Raised as a "delayed" refactor finding (DUP-2) during the dev-loop for s08t2305.

## Sites (non-exhaustive)

- `tests/cli/test_merge.py` around lines 725-735, 763-770, 787-794, 825-836, 848-859 (orphan / untracked test classes).

## Decisions & constraints

- Add a helper such as `register_two_sources(git_repo, other_repo, ...)` in `tests/cli/helper.py` (or let `register_source` be callable twice without clobbering the shared registry), then collapse the repeated blocks to a single call.
- Behavior-preserving — assertions and expected values unchanged.
- Keep it focused on the two-source fixture; do not fold in the single-source `register_source` override pattern.

## Acceptance criteria

- The repeated two-source setup blocks collapse to a shared helper call.
- All existing tests still pass unchanged in intent.
- `uv run tox` green.
