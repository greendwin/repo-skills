---
id: s04t09
slug: rework-statuspy-internals-to-typed
status: pending
---

# Rework `_status.py` internals to typed structures

Refactor `_status.py` data flow to use typed structures instead of raw dicts and loose tuples.

`src/repo_skills/cli/_status.py` · `status()`:
> TODO: rework all this method to typed structures (too many raw strings now)
>       (e.g. don't store skill_name, but manifest entry itself, and so on)

`src/repo_skills/cli/_status.py` · `_scan_sources()`:
> TODO: rework ret type to named tuple

Replace `SkillsBySource` (raw `dict[str, list[str]]`) and the 3-tuple return from `_scan_sources` with named types. Pass manifest entries instead of bare skill names where useful.

Remove the TODOs once fixed.
