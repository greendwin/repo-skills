---
id: s08t34
slug: relocate-skillmd-frontmatter-reader-and
status: done
---

# Relocate SKILL.md frontmatter reader and dedup SKILL.md constant

Follow-up from s08t27 (refactor phase, delayed).

`read_skill_description` currently lives in `src/repo_skills/config/_source.py`, whose cohesion is the Source/SourceConfig/SourceSkill domain. The function is a generic SKILL.md frontmatter reader operating on installed provider paths, not sources.

Move it into a dedicated SKILL.md/frontmatter module (e.g. `config/_skill_md.py`) that owns the `SKILL.md` filename constant plus the frontmatter reader, keeping the public re-export from `repo_skills.config` unchanged. Fold in the pre-existing duplicated constant: `SKILL_FILE = "SKILL.md"` in `config/_source.py:14` and `_SKILL_FILE = "SKILL.md"` in `discovery.py:10` — single source of truth.

Behavior-preserving; existing tests for `read_skill_description` and orphan-merge commit messages must stay green.
