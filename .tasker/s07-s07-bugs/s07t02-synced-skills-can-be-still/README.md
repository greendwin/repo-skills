---
id: s07t02
slug: synced-skills-can-be-still
status: pending
---

# Detect and handle detached skills (unreachable commits)

## Context

Skills can show as "synced" in `skills status` even though their stored commit is no longer reachable from the pinned branch (e.g. after a force-push or branch rewrite). `skills update` should detect this, mark the skill as detached, and `skills merge` should handle detached, mergeable, and orphan skills gracefully — with appropriate reachability checks and base commit search.

## Decisions

- **Preserve manifest entry with `detached` flag instead of removing it.** Keeps the stored commit and baseline hashes so tracking can auto-recover if the commit becomes reachable again. *Rejected: removing the entry (loses history, requires `install --force` to re-track).*
- **Flag name is `detached`, not `untracked`.** "Untracked" is an umbrella concept (detached + orphan + mergeable), not a manifest field. "Detached" precisely describes the state: was installed, commit lost.
- **`skills update` checks reachability inline** as each skill is processed. Uses `is_ancestor(commit, pinned_branch)`. Marks detached if unreachable, auto-recovers if a previously detached commit becomes reachable again. Skips skills with `commit=None`.
- **Only report state changes.** Print when a skill becomes detached or recovers. Stay silent if state hasn't changed since last update.
- **`skills status` treats detached skills as mergeable/orphan.** Detached entries are excluded from `installed_by_source`, falling through to existing display logic. No new UI concept.
- **Installed files are never deleted without explicit user action.** When a skill becomes detached, only the manifest flag changes. Files remain functional in the provider.
- **`skills merge` three-tier commit reachability:**
  - Reachable from pinned branch → proceed normally.
  - Exists but not on pinned branch → stop, suggest `--search-base` (avoids merging unrelated history from other branches). *Rejected: cherry-pick (adds complexity), auto-proceed (drags in unrelated changes).*
  - Fully dangling → auto-search via `_find_base_commit` (user can't do anything useful with a dangling commit).
- **`--search-base` flag** forces base commit search regardless of reachability state.
- **Base commit search reports: commit hash + distance (line count) + first line of commit message.**
- **Mergeable skills (no manifest entry) support in merge.** Compute hashes from installed copy, search git history for base. If exact match found, create manifest entry (not a no-op — tracking is the point). If close match, use as base with normal merge flow.
- **Orphan merge uses a simple separate path.** Switch to pinned branch, copy files to skills dir, commit (or `--no-commit`). Create manifest entry after. No merge branch machinery.
- **Orphan source selection:** auto-pick if one source registered, require `--source` if multiple.
- **Two new `GitRepo` protocol methods:** `is_ancestor(commit, branch)` and `commit_exists_in_any_branch(commit)`.

## Out of scope

- Changing `skills status` to perform reachability checks (it stays lightweight/hash-based).

## Subtasks

- [x] [s07t0201](s07t0201-orphan-merge-simple-copy-path.md): Orphan merge (simple copy path)
- [x] [s07t0202](s07t0202-searchbase-and-search-reporting.md): --search-base and search reporting
- [x] [s07t0203](s07t0203-gitrepo-protocol-isancestor-and-commitexistsinanybranch.md): GitRepo protocol: is_ancestor and commit_exists_in_any_branch
- [x] [s07t0204](s07t0204-update-detached-detection-and-autorecovery.md): Update detached detection and auto-recovery
- [x] [s07t0205](s07t0205-status-display-for-detached-skills.md): Status display for detached skills
- [ ] [s07t0206](s07t0206-merge-threetier-commit-reachability.md): Merge three-tier commit reachability
- [ ] [s07t0207](s07t0207-merge-for-mergeable-skills-no.md): Merge for mergeable skills (no manifest entry)
