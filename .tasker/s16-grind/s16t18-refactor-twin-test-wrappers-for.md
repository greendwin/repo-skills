---
id: s16t18
slug: refactor-twin-test-wrappers-for
status: pending
---

# Refactor: Twin test wrappers for legacy-state cleanup duplicate the same 6-line boilerplate

## Refactor side-task
- depth: 2
- origin: s16t08 — refactor finding "Twin test wrappers for legacy-state cleanup duplicate the same 6-line boilerplate"

## Goal

Apply the deferred refactoring surfaced while processing s16t08.
- location: tests/cli/test_merge.py:2031 (TestMergeContinue.test_unlinks_orphaned_merge_state) and :2254 (TestMergeAbort.test_unlinks_orphaned_merge_state)
- severity: nit

Both methods are byte-identical except for the trailing CLI verb ("--continue" vs "--abort") passed to the already-shared `_assert_unlinks_orphaned_merge_state` helper. The behavior body is correctly extracted, but the two thin wrappers still repeat the same fixture signature and call shape; this is the standard cost of pytest class-scoping rather than true copy-paste, so unification buys little.

## Suggested fix

Acceptable as-is given pytest's class-per-command grouping. If consolidation is desired, parametrize a single test over the verb (e.g. `@pytest.mark.parametrize("verb", ["--continue", "--abort"])`) in one location and drop the per-class wrappers — at the cost of losing the natural grouping under TestMergeContinue/TestMergeAbort.
