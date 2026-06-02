---
id: s06t1902
slug: skillsdir-option-with-strict-validation
status: pending
---

# `--skills-dir` option with strict validation

## Goal

Add a `--skills-dir` option that sets the skills root on fresh init (overriding auto-detection) and edits it on reinit. The path is strictly validated; reinit feedback shows a `skills_dir: old → new` change line.

## Decisions & constraints

- **Skills root** is the domain concept (defined in `CONTEXT.md`); the option is `--skills-dir`, consistent with the `SourceConfig.skills_dir` field and `detect_skills_dir`.
- **Strict validation** — the path must be relative, inside the repo, and already exist as a directory; otherwise a clear error (e.g. `Skills dir 'foo' not found in repo.`). Reject absolute paths and `../` escapes with the same error. *Rejected: lenient create-if-missing (a typo silently scatters empty dirs); split strict-on-edit / lenient-on-create.*
- The no-flag bootstrap of `skills/` (with `.gitkeep`) stays only on the auto path.
- **No manifest migration** when skills_dir changes — a now-absent skill reports "skill removed from source" on next `update` (existing `_SkillError`); newly-exposed skills show as available. No migration code.

## Edge cases

- Missing directory; absolute path; `../`-escaping path → error.
- Valid edit changing the stored value → `skills_dir: old → new` feedback line.
- Honored on both fresh init (override detection) and reinit.

## Key files

- `src/repo_skills/cli/_source.py`
- `tests/cli/test_source_init.py`

## Acceptance criteria

- `--skills-dir` sets the value on fresh init and edits it on reinit.
- Non-existent, absolute, and repo-escaping paths each error clearly.
- Reinit emits a `skills_dir: old → new` change line.
