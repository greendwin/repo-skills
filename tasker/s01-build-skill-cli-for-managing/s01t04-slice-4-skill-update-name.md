---
id: s01t04
slug: slice-4-skill-update-name
status: pending
---

# Slice 4 — `skill update [name]`

**Goal:** Update one or all installed skills from repo. Skip unchanged (same commit hash), abort on conflict (both sides modified) with warning pointing to `skill peek --diff` and `skill merge`.
**Decisions:** No-arg updates all, named arg updates one, abort on conflict.
**Key files:** `src/skill_cli/_main.py`, tests
