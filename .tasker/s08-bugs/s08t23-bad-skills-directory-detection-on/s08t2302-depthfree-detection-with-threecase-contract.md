---
id: s08t2302
slug: depthfree-detection-with-threecase-contract
status: done
---

# Depth-free detection with three-case contract

## Goal

`detect_skills_dir` finds skills at any nesting depth and returns a typed result distinguishing three situations, instead of overloading `None`. Pure detection logic — `source init` consumes it in the next slice.

## Decisions & constraints

- **Walk depth & pruning** — Drop `_MAX_DETECT_DEPTH` entirely. Keep skipping dot-prefixed dirs (e.g. `.git`). Once a dir contains `SKILL.md`, record it and `dirnames.clear()` so the walk never descends into a skill's internals. This finds skills at any depth — the root-cause bug was the cap clearing `dirnames` *before* the `SKILL_FILE` check, hiding depth-3 skills like `claude/skills/grill-me/SKILL.md`. *Rejected: keeping a raised cap with the check moved before the clear — the cap is arbitrary and already caused this bug; the glossary already promises leaf-name identity regardless of nesting depth.*
- **Three-case detection contract** — Return a typed result (e.g. an enum/dataclass `DetectResult{ kind: NONE | SINGLE | AMBIGUOUS, path: Path | None }`) so the caller can tell "no skills exist" (→ fall back to default dir) apart from "skills exist but their deepest common ancestor is the repo root" (→ ambiguous, require manual list). Today both collapse to `None`, which is exactly the bug — `None` was treated as "no skills" and triggered the empty-`skills/` fallback even when skills existed.
  - NONE — no `SKILL.md` anywhere.
  - SINGLE — skills found and their deepest common ancestor is **below** the repo root → `path` is that dir.
  - AMBIGUOUS — skills found but the deepest common ancestor **is** the repo root.
- Reuse the existing deepest-common-ancestor logic over the skill dirs' parents.

## Edge cases

- Skills directly under the repo root (e.g. top-level `tdd/SKILL.md`, `grill-me/SKILL.md`) → parents are the repo root → AMBIGUOUS (correct: scanning the whole repo root must be an explicit user choice).
- A single skill whose parent is below root → SINGLE.
- Skills nested under a category (`skills/cat/grill-me/SKILL.md`) → pruning stops at `grill-me`; common ancestor computed over parents still resolves to `skills` when combined with `skills/tdd`.
- A `SKILL.md` nested inside another skill dir must not be visited (pruned).
- Empty repo / only dot-dirs → NONE.

## Key files

- `src/repo_skills/discovery.py` — `detect_skills_dir`, `_deepest_common_ancestor`, `_MAX_DETECT_DEPTH` (remove), `find_git_root` (keep).
- Tests: `tests/test_discovery.py` (the `detect_skills_dir` coverage; note `find_repo_skills_dir` tests are removed in the dead-code slice, not here). Use pyfakefs (`FakeFilesystem`), not real fs.

## Acceptance criteria

- A repo with `claude/skills/grill-me/SKILL.md` and `claude/skills/tdd/SKILL.md` returns SINGLE with path `claude/skills`.
- A repo with `claude/skills/grill-me/SKILL.md` and `copilot/foo/SKILL.md` returns AMBIGUOUS.
- A repo with no `SKILL.md` returns NONE.
- A skill at depth 4+ (`a/b/c/skill/SKILL.md`) is still found (no depth cap).
- Dot-dirs are not walked; a `SKILL.md` inside an already-detected skill dir is not separately recorded.
- `uv run tox` green.
