---
id: s08t32
slug: reduce-scaffolding-duplication-in-testreadskilldescription
status: done
---

# Reduce scaffolding duplication in TestReadSkillDescription

Follow-up from s08t27 (review, out-of-scope nit).

In `tests/test_config.py`, the new `TestReadSkillDescription` cases each repeat the same two-line preamble — `skill_dir = Path("/skills/tdd")` then `fs.create_file(skill_dir / "SKILL.md", contents=...)` — varying only the `contents=` payload and the expected return value.

Reduce the duplication, e.g. a small local helper `write_skill(fs, contents) -> Path` or a `pytest.mark.parametrize` over `(contents, expected)` collapsing the present/empty/whitespace/trim/CRLF/no-frontmatter/no-description cases into one table-driven test. Keep the per-case literals legible — do not over-abstract. Behavior-preserving; no production change.
