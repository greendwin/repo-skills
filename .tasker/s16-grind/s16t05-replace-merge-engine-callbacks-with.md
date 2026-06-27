---
id: s16t05
slug: replace-merge-engine-callbacks-with
status: in-progress
---

# Replace merge-engine callbacks with a discriminated result object

Follow-up refactor from s08t40 (delayed). `_run_branch_merge` in `src/repo_skills/cli/_merge.py` is parameterized by two closures — `on_exact_match` and `on_finalize` — which force each caller (`_merge_start`, `_merge_retarget`) to capture 4-6 free vars into lambdas defined ~100 lines apart from the engine.

Goal: replace the two `Callable` params with a returned discriminated `MergeOutcome` (e.g. `EXACT_MATCH(commit)`, `DEFERRED`, `FINISHED(branch_name, use_merge)`). Each caller then `match`es on the outcome linearly (exact-match branch, deferred → return, finished → run finalize inline). Deletes the closure indirection and hidden capture; makes both callers top-to-bottom readable.

Subsumes two smaller deferred nits: the `on_finalize` signature passes `git` (callers already close over it) and a `branch_name` the same-source caller discards (T5/general#4); and the engine docstring over-states the variation axes (T6).

Taste-dependent re-architecture of a freshly-landed seam — do test-first against the full `tests/cli/test_merge.py` matrix; behavior must stay byte-identical. The general code-review lens did NOT object to the current callback design, so this is a quality/readability improvement, not a correctness fix.
