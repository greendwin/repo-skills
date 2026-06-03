---
id: s06t1803
slug: derive-pulls-from-the-collected
status: in-review
---

# Derive pulls from the collected skill set

## Goal

Only sources that own at least one target skill are pulled. A registered source with no installed skills is never pulled — including on a no-arg `update`. `skills update -s X` pulls only source `X`.

## Decisions & constraints

- **Pulls derived from the collected set** — after collection, map target skills to their sources (via manifest `entry.source`) and pull only those. *Rejected: keep pulling all registered sources up front.*
- Accepted behavior change: an idle registered source (zero installed skills) is no longer pulled even on no-arg `update` — an efficiency fix.
- **Empty-check positioning** — the no-op/empty determination must run *after* collection, leaving room for s06t16 attach-candidates to extend the set before the check fires.
- One `Pulling <source>` line per derived source only.

## Edge cases

- No-arg `update` with one idle registered source → that source is not pulled.
- `-s X` → only `X` is pulled.

## Key files

- `src/repo_skills/cli/_update.py`
- `tests/cli/test_update.py`

## Acceptance criteria

- The set of pulled sources equals the sources of the collected skills.
- An idle registered source is not pulled on no-arg `update`.
- `-s X` pulls only `X`.
