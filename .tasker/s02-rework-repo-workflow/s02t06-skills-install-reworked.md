---
id: s02t06
slug: skills-install-reworked
status: done
---

# `skills install` (reworked)

**Goal:** Rework install to use new models. Resolves source, installs to all providers, records source/commit/hashes in manifest. `--force` to overwrite. Collision detection.
**Decisions:** Install targets all providers, `--force` one at a time, collision rejected.
**Key files:** `src/repo_skills/main.py`, `src/repo_skills/discovery.py`, tests
