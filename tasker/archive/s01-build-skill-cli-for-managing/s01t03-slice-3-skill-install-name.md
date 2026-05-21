---
id: s01t03
slug: slice-3-skill-install-name
status: done
---

# Slice 3 — `skill install <name>` + `skill uninstall <name>`

**Goal:** Copy skill from repo to `~/.claude/skills/`, write manifest entry (repo path + commit hash). Remove skill + manifest entry. GitRepo methods added as needed (get root, current commit).
**Decisions:** File copy install, manifest tracks repo path + commit hash, thin git wrapper.
**Key files:** `src/skill_cli/_git.py`, `src/skill_cli/_manifest.py`, `src/skill_cli/_main.py`, tests
