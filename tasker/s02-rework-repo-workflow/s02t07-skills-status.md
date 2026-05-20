---
id: s02t07
slug: skills-status
status: in-review
---

# `skills status`

**Goal:** Show per-source skills, per-provider divergence (synced/modified/missing), source freshness. No git pull. Uses baseline hashes.
**Decisions:** Divergence via per-file hashes, no git pull on status.
**Key files:** `src/repo_skills/main.py`, tests
