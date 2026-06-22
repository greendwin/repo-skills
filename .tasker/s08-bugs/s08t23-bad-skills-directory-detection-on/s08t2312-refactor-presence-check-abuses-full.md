---
id: s08t2312
slug: refactor-presence-check-abuses-full
status: done
---

# Refactor: Presence check abuses full detection walk (detect_skills_dir) for a yes/no answer

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "Presence check abuses full detection walk (detect_skills_dir) for a yes/no answer"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/cli/_source.py:143-144 (_dir_has_skills)
- severity: minor

DEDUP: this collapses five overlapping findings (the thermo-nuclear, performance x3, and duplicate-location reports), all targeting `_dir_has_skills` at _source.py:143-144 delegating to detect_skills_dir; strongest severity kept (minor). _dir_has_skills only needs to know whether ANY SKILL.md exists under the dir, but it calls detect_skills_dir(path), which does a full os.walk collecting every skill dir AND computes a deepest-common-ancestor across all of them, then discards everything except 'kind is not NONE'. This is the wrong abstraction for the question being asked: it pays for the whole detection algorithm (and its AMBIGUOUS/SINGLE branching) to answer a boolean. It is also a regression versus the removed resolve_skills_dir which did a single is_dir() stat. It couples a CLI-layer presence note to the detection contract, so future changes to detection semantics silently change the warning behaviour. Adding a new public discovery helper (has_any_skill) extends the discovery module's API beyond this slice's scope, so it is routed to delayed.

## Suggested fix

Add a short-circuiting predicate in discovery.py, e.g. `def has_any_skill(root: Path) -> bool` that os.walks pruning dotdirs and returns True on the first dir whose filenames contain SKILL_FILE (clearing dirnames to skip a skill's internals), returning False if the walk completes. Then `_dir_has_skills` becomes `return path.is_dir() and has_any_skill(path)`. This drops the DetectKind/detect_skills_dir import coupling from the presence check and avoids accumulating all skill dirs plus the common-ancestor computation, returning as soon as one SKILL.md is seen.
