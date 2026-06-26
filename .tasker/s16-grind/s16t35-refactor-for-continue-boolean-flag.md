---
id: s16t35
slug: refactor-for-continue-boolean-flag
status: pending
---

# Refactor: `for_continue` boolean flag splits `_resolve_active_merge` into two behaviors (flag-argument smell)

## Refactor side-task
- depth: 2
- origin: s16t10 — refactor finding "`for_continue` boolean flag splits `_resolve_active_merge` into two behaviors (flag-argument smell)"

## Goal

Apply the deferred refactoring surfaced while processing s16t10.
- location: src/repo_skills/cli/_merge.py:1053 (_resolve_active_merge signature) / call sites 1079-1081, 1170-1172
- severity: minor

`for_continue` is a control-flow flag: it exists solely to toggle the legacy-keep refusal that only `_merge_continue` wants. `_merge_abort` must pass `for_continue=False` purely to opt out, which is noise at the call site and couples abort to a concern it does not share. The shared responsibility of `_resolve_active_merge` is really just 'locate the in-progress merge (repo/branch/parsed names) + legacy cleanup'; the refusal is continue-specific policy. Restructuring the resolve seam and lifting policy into the continue path is structural work touching multiple call sites — route as a side-task seed rather than forcing it in this slice.

## Suggested fix

Drop the `for_continue` parameter: keep `_resolve_active_merge` returning the `_ActiveMerge` (locate + cleanup only), and lift the legacy-keep refusal into `_merge_continue` as a small guard `_guard_legacy_keep_source(branch)` invoked before `_resolve_active_merge` cleans up — or have `_merge_continue` call a thin `_resolve_active_merge_for_continue` wrapper. `_merge_abort` then calls `_resolve_active_merge(ctx)` with no flag.
