---
id: s08t2305
slug: orphan-merge-target-active-dir
status: done
---

# Orphan merge target = active dir

## Goal

When `merge` writes a merged orphan skill back into the source repo, it lands in the source's active dir (`skills_dirs[0]`) rather than the old single `skills_dir`.

## Decisions & constraints

- **Active dir = first entry** — `_merge.py` currently builds `skill_rel_path = f"{source.config.skills_dir}/{skill_name}"`. Change it to use `source.config.skills_dirs[0]` — the first dir is the active/merge target, the semantics adopted across this task. `_copy_skill_with_replace` already creates parent dirs, so a not-yet-existing active dir is fine.
- **Non-empty guaranteed** — `source init` guarantees `skills_dirs` is non-empty for any source it writes (NONE/SINGLE produce one entry; AMBIGUOUS errors; explicit list requires ≥1). A defensive assert/guard before indexing `[0]` is cheap and worth adding to fail loudly on a hand-corrupted config.

## Edge cases

- Active dir does not yet exist on disk → created on copy (current behavior, just under the new path).
- A migrated v0 config yields `skills_dirs=[old_value]`, so existing single-dir sources merge to exactly the same place as before (no behavior change for them).

## Key files

- `src/repo_skills/cli/_merge.py` — `_merge_orphan` (around the `skill_rel_path` construction).
- `src/repo_skills/config/_source.py` — `SourceConfig.skills_dirs`.
- Tests: `tests/cli/test_merge.py` (the orphan-merge scenarios; many `SourceConfig(..., skills_dir="skills")` constructions migrate to `skills_dirs=["skills"]` in slice 1, so assert the orphan lands under the first dir).

## Acceptance criteria

- Merging an orphan into a source with `skills_dirs=["claude/skills", "copilot"]` writes the skill under `claude/skills/<name>` and commits it there.
- A migrated single-dir source (`skills_dirs=["skills"]`) merges the orphan to `skills/<name>` exactly as before.
- A config with empty `skills_dirs` fails loudly (assert/guard) rather than `IndexError`.
- `uv run tox` green.
