---
id: s02t11
slug: rename-installed-skills-on-source
status: done
---

# Rename installed skills on source rename

**Goal:** When `skills source init --name new-name` renames a source that has installed skills, update the installed skill entries in `SkillManifest` to reference the new source name. Currently blocked with `AppError("Renaming installed skills is not yet supported.")`.\n**Key files:** `src/repo_skills/cli/_source.py` (`_has_installed_skills`), `src/repo_skills/_config.py` (`SkillManifest`, `SkillEntry.source`)
