---
id: s08t2316
slug: refactor-repeated-skills-dir-values
status: done
---

# Refactor: Repeated --skills-dir values are stored verbatim without de-duplication

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "Repeated --skills-dir values are stored verbatim without de-duplication"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_source.py:127
- severity: nit

DEDUP: collapses the two overlapping dedup findings (both at _normalize_skills_dirs, _source.py:127-140); strongest severity kept (nit). _normalize_skills_dirs appends every resolved dir unconditionally, so `--skills-dir a --skills-dir a` (or `--skills-dir a --skills-dir ./a`, both normalizing to `a`) yields config.skills_dirs == ['a', 'a']. The first dir is the active/merge-target dir and a later multi-dir scan slice scans all dirs for collisions; duplicate entries could double-count or make every leaf collide with itself (collision rule, ADR-0005), potentially excluding skills. Not exercised by this slice and not a present bug. The concern interacts with a future multi-dir-scan slice and the spec is silent on dedup, so it is routed to delayed as a robustness seed rather than forced in place.

## Suggested fix

After normalization, drop duplicates while preserving first-seen order, e.g. `normalized = list(dict.fromkeys(normalized))`, so the active dir (first occurrence) is retained and repeats are dropped; only emit the 'no skills' note for newly added dirs.
