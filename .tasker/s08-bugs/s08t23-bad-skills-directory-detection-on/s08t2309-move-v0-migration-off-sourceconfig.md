---
id: s08t2309
slug: move-v0-migration-off-sourceconfig
status: pending
---

# Move v0 migration off SourceConfig into a dedicated _SourceConfigV0 model

## Context

s08t2301 implemented v0→v1 migration by keeping a migration-only field on the permanent model:

    skills_dir: str | None = Field(default=None, exclude=True)  # parsed from v0, never serialized

This was a deliberate, recorded decision in s08t2301 ("keep a `skills_dir: str | None` field used only during migration"). The downside flagged in refactor review: the v0-only field is a tombstone that lives forever on `SourceConfig` — every reader sees two directory fields and must know one is dead; and to let legacy JSON validate, `name`/`skills_dirs` were loosened to defaults, weakening the v1 contract.

## Decision needed (supersedes the s08t2301 decision)

Reshape migration so the legacy shape is parsed by a dedicated model used only inside `load_source_config`:

- Add `_SourceConfigV0(VersionedConfig)` with `skills_dir: str = ""` (and `name`/`branch`).
- In the OUTDATED branch, parse the raw JSON as `_SourceConfigV0`, then construct a clean `SourceConfig(name=..., skills_dirs=[skills_dir] if skills_dir else [], branch=...)` and re-save.
- Remove the `skills_dir` tombstone field, its comment, and the `cfg.skills_dir = None` reset from `SourceConfig`.
- Reconsider tightening `name` back to required on `SourceConfig` (note `Source.name` already falls back to `repo_root.name`); keep `skills_dirs` tolerant of `[]` per the parent story.

## Caveats / scope

- `load_versioned_config` hands back a parsed `cfg` of the requested model — confirm the v0 parse path fits cleanly (may need to read raw JSON for the v0 branch).
- Keep all s08t2301 acceptance criteria green (legacy migrate preserves name/branch, drops `skills_dir` key, writes v1; v1 no-resave; v2 raises; absent/empty → `[]`).
- `uv run tox` green.

Surfaced by /dev-loop refactor triage on s08t2301 (delayed finding; reverses the migration-field approach recorded in s08t2301).
