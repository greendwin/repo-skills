---
id: s06t1801
slug: extract-targetskill-collection-as-a
status: done
---

# Extract target-skill collection as a seam

## Goal

`update` computes its work set through a single collection function (e.g. `_collect_targets(manifest, name, source=None)`) returning the skills to process. No-arg and positional-name behavior is unchanged; existing update tests pass untouched. This is a pure refactor toward the unified collection model — the seam that later slices and s06t16 extend.

## Decisions & constraints

- **Unified collection model** — `update` becomes *collect target skills → derive sources to pull → process*. This slice introduces only the collection function; behavior stays identical. *Rejected: special-casing each filter beside the existing all/one-skill branches — doesn't generalize.*
- The collection function is the single place that decides the work set; everything downstream consumes its output.
- No new options or behavior changes in this slice.

## Edge cases

- Empty manifest still raises the existing `No skills installed.` NoopError.

## Key files

- `src/repo_skills/cli/_update.py`
- `tests/cli/test_update.py`

## Acceptance criteria

- Existing update scenarios (no-arg updates all; positional name updates one; unknown name errors) pass unchanged.
- The work set is funneled through one collection function (verified behaviorally via the existing all/one-skill tests).
