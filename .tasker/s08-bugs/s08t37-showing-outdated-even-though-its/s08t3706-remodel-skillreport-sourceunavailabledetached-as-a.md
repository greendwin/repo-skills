---
id: s08t3706
slug: remodel-skillreport-sourceunavailabledetached-as-a
status: done
---

# Remodel _SkillReport source-unavailable/detached as a discriminated outcome

## Goal

Replace the `_SkillReport.detached_override: bool | None` + `source_unavailable: bool` flag pair (in `src/repo_skills/cli/_update.py`) with a first-class model so the source-unavailable case is an explicit outcome rather than an override that short-circuits the derived `detached` property.

## Context

Surfaced by the refactor (thermo-nuclear) lens during dev-loop review of s08t3704. The current code is correct and fully tested — this is a readability/modeling improvement only (behavior-preserving).

The smell: `_SkillReport` models attach/detach transitions cleanly via the `_Detach` enum and a derived `detached` property, but the source-unavailable case doesn't fit that model, so two escape hatches were bolted on:
- `source_unavailable: bool` — consumed by `_print_skill_report` as an early-return special case.
- `detached_override: bool | None` — short-circuits the `detached` property to preserve `entry.detached` (a real fourth state — "we didn't look, keep prior detach state" — smuggled in as a nullable bool).

## Approach (suggested, not binding)

- Add a `_Detach` variant (e.g. `UNKNOWN`/`UNAVAILABLE`) meaning "source not synced, preserve prior detach state," and have the `detached` derivation map it to `entry.detached`; delete `detached_override`.
- Consider modelling the report outcome as a discriminated union (synced / skipped / source-unavailable) so `_print_skill_report` doesn't need a top-level early-return special case.

## Constraints

- Behavior-preserving: no change to reported labels or manifest outcomes; existing tests for source-unavailable skip and detach reconciliation must pass unchanged.
- `uv run tox` green (all environments).
