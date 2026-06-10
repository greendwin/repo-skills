---
id: s06t1301
slug: extract-shared-skillclassification-module
status: pending
---

# Extract shared skill-classification module

## Goal

Factor the skill-classification logic out of `_status.py` into a single reusable function that, given the config context, classifies every installed copy into its state (`synced`/`modified`/`mergeable`/`orphan`/`detached`, plus the non-candidate states `outdated`/`available`/`missing` as relevant). Refactor `status` to consume it. This is a behavior-preserving extraction: `status` output and all existing tests stay green. No new user-facing behavior.

## Decisions & constraints

- **Mirror `status` classification exactly** — this shared function becomes the single source of truth so that the later auto-detect layers and the `status` command can never disagree. Auto-detect (Slice 2) will consume the same function.
- A **detached** skill (tracked, stored commit no longer reachable) must classify as `mergeable`/`orphan`, never `modified` — matching how `status` already presents it (`_group_installed_by_source` excludes detached; `_collect_untracked` treats it as untracked).
- Preserve current `status` rendering and ordering precisely. The existing string constants (`STATUS_MODIFIED`, etc.) and table formatting stay; only the classification computation moves.
- Reuse, don't duplicate: the new module should subsume `_check_divergence`, `_collect_untracked`, and the modified/mergeable/orphan determination currently spread across `_status.py`.

## Edge cases

- Skill installed under multiple providers with differing states (e.g. modified in one, synced in another) — classification must be expressible per (skill, provider) so callers can aggregate as needed.
- Detached skills (baseline present but commit unreachable) -> mergeable/orphan, not modified.
- Broken sources / missing provider install dirs — keep current tolerant handling.

## Key files

- `src/repo_skills/cli/_status.py` (extract from here)
- new shared module (e.g. `src/repo_skills/` classification helper; submodule `_`-prefixed per project convention)
- `tests/cli/test_status.py` (must stay green); add unit tests for the extracted function

## Acceptance criteria

- A single function returns the classification for installed copies usable by both `status` and merge.
- `skills status` output is byte-for-byte unchanged (existing tests pass).
- Detached skills classify as mergeable/orphan, never modified, with a direct unit test.
- `uv run tox` passes (all environments), including pre-existing issues.
