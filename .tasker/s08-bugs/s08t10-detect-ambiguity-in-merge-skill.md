---
id: s08t10
slug: detect-ambiguity-in-merge-skill
status: done
---

# Detect ambiguity in merge skill resolution (sources + providers)

Same "pick-first" bug class as s08t01, at two more sites. Skills are identified by leaf name across sources/providers, so collisions are reachable.

`_merge.py` `_resolve_untracked`:
> TODO: BUG: multiple sources can have the same skill

Fix: honor the existing `--to-source` flag; when absent and >1 registered source contains the skill name, raise `AppError` (hint: use `--to-source`). Remove the TODO once fixed.

`_merge.py` `_find_in_provider`:
> TODO: BUG: multiple providers can have same skill, but we peak only the first one
> need to detect ambiguity

Fix: collect all matching providers; >1 → `AppError` (hint: use `--from`), mirroring the existing ambiguity check in `_resolve_diverged_provider`. Honor `--from` when given. Remove the TODO once fixed.

Add tests for both ambiguity paths (TDD).
