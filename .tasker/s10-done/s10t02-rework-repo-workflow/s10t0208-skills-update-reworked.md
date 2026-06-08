---
id: s10t0208
slug: skills-update-reworked
status: done
---

# `skills update` (reworked)

**Goal:** Multi-source/multi-provider update. Git pull by default. Auto-installs to new providers. Skips modified copies. No `--force`.
**Decisions:** Update pulls, auto-install new providers, skip modified.
**Key files:** `src/repo_skills/main.py`, tests
