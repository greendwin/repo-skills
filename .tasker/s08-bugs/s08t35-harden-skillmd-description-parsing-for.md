---
id: s08t35
slug: harden-skillmd-description-parsing-for
status: done
---

# Harden SKILL.md description parsing for quoted and block-scalar values

Follow-up from s08t27 (refactor phase, delayed).

`read_skill_description` (`src/repo_skills/config/_source.py`) parses only unquoted single-line `description:` values. Real SKILL.md frontmatter sometimes quotes the value (`description: "Does X"`) or uses YAML block scalars (`description: >` / `description: |`). Currently:
- a quoted value returns the literal text including surrounding quotes, and
- a block-scalar indicator returns `>` or `|` as the description.

Both produce an ugly (but non-fatal) commit body when merging an orphan skill.

Harden the parser: strip a single matched pair of surrounding single/double quotes, and treat a value of exactly `>`, `|`, `>-`, `|-` as "no inline description" (return `None`). Avoid pulling in a YAML dependency / half-correct YAML emulation — keep it a focused, well-tested line scan. Add unit tests for quoted values and block-scalar indicators.
