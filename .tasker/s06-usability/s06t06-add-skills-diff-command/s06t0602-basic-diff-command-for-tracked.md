---
id: s06t0602
slug: basic-diff-command-for-tracked
status: pending
---

# Basic diff command for tracked modified skill

**Goal:** `skills diff <name>` produces colored unified diff for a tracked skill with local edits. Covers the happy path: skill in manifest, source available, files modified. Includes `--from` flag for provider disambiguation.

**Decisions:**
- Baseline vs installed copy (what user changed locally)
- Read baseline from source repo at `entry.commit`
- Unified diff with Rich coloring (`+` green, `-` red, `@@` cyan via `echo()`)
- Single skill name argument
- `--from` flag for provider disambiguation

**Key files:** `src/repo_skills/cli/_diff.py` (new), `src/repo_skills/cli/__init__.py`, `tests/cli/test_diff.py` (new)
