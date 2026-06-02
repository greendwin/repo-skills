---
id: s06t19
slug: allow-to-edit-source-skills
status: pending
---

# Allow to edit `source` skills directory

## Context

`source init` reinit (`_handle_reinit`) edits only `name`/`branch`; the skills dir is fixed after first init. Separately, `skills init` is a hidden command that just errors with a "did you mean `skills source init`?" hint (s06t10). Resolving both grew into a small command-surface redesign captured in **ADR 0003**. The "Skills root" concept is now defined in `CONTEXT.md`.

Independent of t18/t16. Implementation order: **t18 → t16 → t19**.

## Decisions

- **`--skills-dir` option (Skills root)** — honored on both create and edit. **Strict validation**: the path must be relative, inside the repo, and already exist as a directory — else a clear error (e.g. `Skills dir 'foo' not found in repo.`). The no-flag bootstrap of `skills/` (with `.gitkeep`) stays only on the auto path. *Rejected: lenient create-if-missing (a typo silently scatters empty dirs); split strict-on-edit / lenient-on-create.*
- **Two intent-named commands over one idempotent impl** (ADR 0003) — `skills init` (visible, "first-time setup") and `skills source config` (visible, "edit settings"), both accept `--name`/`--branch`/`--skills-dir`, both create-if-absent / edit-if-present. They must share a single implementation so they can't drift. `skills source init` is kept as a **hidden back-compat alias**; the old hidden `init`-redirect command is removed. **Supersedes s06t10's** "don't silently forward" decision. *Rejected: one overloaded `source init`; dropping `source init` entirely (breaks muscle memory/tests for no gain pre-1.0).*
- **No manifest migration when skills_dir changes** — a now-absent skill reports "skill removed from source" on next `update` (existing `_SkillError`); newly-exposed ones show as available. Document only, no migration code.
- **Update `CONTEXT.md` "Source" definition** to cite `skills init` / `skills source config` instead of `skills source init` — done at implementation time, when the commands exist.

## Open questions

- None.

## Out of scope

- Manifest migration on skills-dir change.
- Multi-source resolution changes (s06t20).

## Subtasks

- [ ] [s06t1901](s06t1901-extract-shared-idempotent-initconfig-implementation.md): Extract shared idempotent init/config implementation
- [ ] [s06t1902](s06t1902-skillsdir-option-with-strict-validation.md): `--skills-dir` option with strict validation
- [ ] [s06t1903](s06t1903-skills-init-skills-source-config.md): `skills init` + `skills source config` command surface
