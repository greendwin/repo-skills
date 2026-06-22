---
id: s08t2304
slug: multidir-scan-collision-exclusion
status: done
---

# Multi-dir scan + collision exclusion

## Goal

`_collect_source_skills` scans every dir in a source's `skills_dirs`, merging the discovered skills. A skill leaf name that appears in more than one dir is a collision: it is excluded entirely and reported inline, but the source stays usable for its other skills.

## Decisions & constraints

- **Multi-dir scan** — Iterate `skills_dirs` in order, walking each for `SKILL.md` (same pruning as detection: record + stop descending at a skill dir). Merge into the `dict[str, SourceSkill]` keyed by leaf name. A missing/non-existent dir in the list is skipped (no error).
- **Collision = drop all copies** — If the same leaf name is found in more than one dir, exclude **all** copies from the resolved skills — do not keep one. *Rejected: first-dir-wins (would silently make `merge`/`update` act on a dir the user didn't choose); raising/aborting (one mirrored skill would make the whole source unusable and blank `status`).*
- **Dedicated error type, printed not raised** — Introduce `SkillNameCollisionError(AppError)` carrying a collision-specific message that names the skill and the conflicting dirs (use the established `props`/`fmt_*` formatting). Do **not** raise it — instead `console.print` it inline using the same rendering the error handler uses (`[red]Error:[/red] {message}`), then continue. The source remains usable for `install`/`update`/`status` minus the collided skill. `config/_source.py` already imports `console`/`fmt_ident`/`fmt_path`, so inline printing is consistent. Each command collects a given source's skills once per run, so no meaningful duplicate spam.

## Edge cases

- Same name in three dirs → still a single collision report for that name; all three dropped.
- A collided name that is also installed (in the manifest) → still dropped from the *source* skill set; `_compute_outdated` already tolerates `source.skills.get(name) is None` (skips). Confirm `status` doesn't crash and the skill simply isn't classified as available/mergeable.
- Non-colliding skills in the same dirs resolve normally.
- `skills_dirs == []` (tolerated from migration) → empty result, no error.

## Key files

- `src/repo_skills/config/_source.py` — `_collect_source_skills` (signature changes to take `skills_dirs: list[str]`), `load_source`.
- `src/repo_skills/errors.py` — add `SkillNameCollisionError(AppError)` (model on `SourceBrokenError`/`ConfigBrokenError`).
- `src/repo_skills/console.py` — `fmt_ident`, `fmt_path`, `fmt_message` for the message; reuse the `[red]Error:[/red]` rendering shape from `error_handler`.
- Tests: `tests/test_config.py`, `tests/cli/test_status.py` (collision scenario), `tests/cli/helper.py`.

## Acceptance criteria

- A source with `skills_dirs=["claude/skills", "copilot"]` where both contain `tdd/SKILL.md` → `tdd` is absent from `source.skills`, and a `[red]Error:[/red]` line naming `tdd` and both dirs is printed.
- Other skills present only once in either dir resolve normally.
- `status` over such a source still renders (does not abort) and lists the non-collided skills.
- A name in three dirs is reported once and fully excluded.
- `uv run tox` green.
