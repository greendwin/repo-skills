---
id: s02t03
slug: skills-source-init
status: in-review
---

# `skills source init`

**Goal:** Implement `source init` with both paths (fresh repo and populated repo). Creates `.repo-skills/` with gitignored `source.json`. Registers in `~/.config/repo-skills/sources.json`. Auto-detects skills dir (max depth 3) or creates with `.gitkeep`.
**Decisions:** `.repo-skills/` dir, source name auto-derived, auto-detection max depth 3, deepest common ancestor guess.
**Key files:** `src/repo_skills/main.py`, `src/repo_skills/discovery.py`, tests
