---
id: s03t02
slug: rename-manifest-file
status: done
---

# Rename manifest file

**Goal:** Change `default_manifest_path()` to return `.skills-manifest.json`. Update any tests that reference the old name. `uv run tox` passes.

**Decisions:**
- Manifest filename → `.skills-manifest.json`

**Key files:** `src/repo_skills/manifest.py`, tests that check manifest path
