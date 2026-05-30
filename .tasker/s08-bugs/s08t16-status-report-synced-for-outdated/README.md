---
id: s08t16
slug: status-report-synced-for-outdated
status: pending
---

# Status report 'synced' for outdated install

## Context

`skills status` reports "synced" for installed skills whose files match the manifest baseline — but this only means "unmodified since install," not "up-to-date with the source." A skill can show "synced" while the source repo has newer commits. Additionally, `get_skill_commit` and `verify_commit_content` hardcode `skills/{skill_name}`, breaking for skills in category subdirectories. Finally, `status` doesn't switch to the pinned branch before scanning, so it may list the wrong set of available/mergeable skills.

## Decisions

- **Replace `skill_name` with `skill_rel_path` in git methods** — `get_skill_commit` and `verify_commit_content` must accept the actual relative path instead of hardcoding `skills/`. The `rel_path` is already available via `SourceSkill.rel_path` at all call sites. *Rejected: keeping `skill_name` and guessing the path (breaks for categorized skills).*
- **Add optional `branch` parameter to `get_skill_commit`** — enables querying `git log -1 --format=%H <branch> -- <path>` without requiring checkout. Needed by `status` to check the pinned branch.
- **Have `status` call `ensure_on_branch` per source** — switches to the pinned branch before scanning skills, consistent with `update` and `merge`. Replaces the separate `--sync` pull loop with `ensure_on_branch(git, branch, pull=sync)`. *Rejected: leaving `status` branch-unaware (produces wrong available/mergeable lists).*
- **Pre-compute outdated skill names** — compare `manifest.commit` vs `get_skill_commit(rel_path, branch=pinned)` to build a `set[str]` of outdated skills. Skip silently when source is broken, commit is `None`, or result is empty. *Rejected: content-based hash comparison (would require reading source files, but status doesn't guarantee the right branch checkout for file content).*
- **New label: `[blue]outdated[/blue]`** — shown when installed matches baseline but source has a newer commit. Combined as `[yellow]modified[/yellow], [blue]outdated[/blue]` when both conditions apply. *Rejected: yellow (conflates with "modified"); red (reserved for "missing").*

## Open questions

None.

## Out of scope

- Changing `update` or `merge` behavior — this task only fixes `status` reporting and the broken git method signatures.

## Subtasks

- [ ] [s08t1601](s08t1601-fix-git-method-signatures-to.md): Fix git method signatures to accept rel_path
- [ ] [s08t1602](s08t1602-have-status-switch-to-pinned.md): Have status switch to pinned branch per source
- [ ] [s08t1603](s08t1603-outdated-detection-and-label-in.md): Outdated detection and label in status
