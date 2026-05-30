---
id: s08t1603
slug: outdated-detection-and-label-in
status: pending
---

# Outdated detection and label in status

## Goal

`status` shows `[blue]outdated[/blue]` when an installed skill's manifest commit differs from the latest source commit on the pinned branch. Shows `[yellow]modified[/yellow], [blue]outdated[/blue]` when both conditions apply.

## Decisions & constraints

- **Pre-compute outdated set** — compare `manifest.commit` vs `get_skill_commit(rel_path, branch=pinned)` to build a `set[str]` of outdated skill names. This is done in the `status` function before printing, keeping `_check_divergence` purely about file-level divergence. *Rejected: content-based hash comparison (would require reading source files on the right branch).*
- **Skip outdated detection silently** when: source is broken (`SourceBrokenError`), manifest commit is `None` (old installs), or `get_skill_commit` returns empty string (skill path not in git history).
- **Label color: blue** — informational "action available" tone. *Rejected: yellow (conflates with "modified"); red (reserved for "missing").*
- Depends on slice 1 (branch-scoped `get_skill_commit`) and slice 2 (pinned branch available in status).

## Edge cases

- `commit: None` in manifest — old installs before commit tracking. Show `synced`/`modified` without outdated.
- Skill removed from source — `get_skill_commit` returns empty. Skip outdated.
- Broken source — already caught by `SourceBrokenError`. Skip outdated.

## Key files

- `src/repo_skills/cli/_status.py` — status command
- `tests/cli/test_status.py` — status tests

## Acceptance criteria

- Skill with matching baseline but newer source commit shows `outdated`
- Skill with modified files and newer source commit shows `modified, outdated`
- Skill with `commit: None` shows `synced`/`modified` without outdated
- Skill from broken source shows normal status without outdated
- Skill where `get_skill_commit` returns empty shows normal status without outdated
