---
id: s01t02
slug: slice-2-repo-discovery-skill
status: done
---

# Slice 2 — Repo discovery + `skill list`

**Goal:** Locate skills repo (git root if inside repo, else manifest's stored path), enumerate repo/installed skills, display with install status and orphans. Manifest model emerges here (read path).
**Decisions:** Repo discovery logic, `skill list` shows repo skills + orphans, manifest at `~/.claude/skills/.skill-install.json`.
**Key files:** `src/skill_cli/_discovery.py`, `src/skill_cli/_manifest.py`, `src/skill_cli/_main.py`, tests
