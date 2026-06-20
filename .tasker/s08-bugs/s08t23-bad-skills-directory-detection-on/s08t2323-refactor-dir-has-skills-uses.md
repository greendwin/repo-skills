---
id: s08t2323
slug: refactor-dir-has-skills-uses
status: in-review
---

# Refactor: _dir_has_skills uses the heavy classification walk just to ask a yes/no question

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "_dir_has_skills uses the heavy classification walk just to ask a yes/no question"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_source.py:152-153 (_dir_has_skills)
- severity: minor

_dir_has_skills only needs to know whether any SKILL.md exists under the dir, but it calls detect_skills_dir, whose job is to *classify* (NONE/SINGLE/AMBIGUOUS) by computing a deepest-common-ancestor over a fully materialized list of every skill dir. Reaching for a classifier and then discarding all of its result except 'is it NONE' is the wrong abstraction: it couples an existence predicate to the full detection algorithm and walks the whole subtree even after the first SKILL.md is found. The intent ('does this dir contain any skill?') is no longer self-evident from the call.

## Suggested fix

Introduce a small predicate in discovery.py, e.g. `def has_any_skill(root: Path) -> bool:` that os.walks pruning dotdirs and returns True on the first `SKILL_FILE in filenames`, then `return path.is_dir() and has_any_skill(path)`. detect_skills_dir can itself be expressed on top of the same walk if desired, keeping one traversal definition.
