---
id: s01t05
slug: slice-5-skill-peek-diff
status: cancelled
---

# Slice 5 — `skill peek [--diff] [name]`

**Goal:** Show both-direction changes (repo→installed, installed→repo). Summary by default (status labels: modified, new, missing, unchanged). `--diff` flag for file-level diffs.
**Decisions:** Both directions, summary + diff flag.
**Key files:** `src/skill_cli/_diff.py`, `src/skill_cli/_main.py`, tests
