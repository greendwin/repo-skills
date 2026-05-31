---
id: s08t17
slug: git-fails-when-nothing-to
status: done
---

# Git fails when nothing to merge

## Context

`skills merge` fails with a git error ("nothing to commit, working tree clean") when `_find_base_commit` finds an exact match (distance=0). This happens because the provider files are byte-identical to a historical commit — creating a branch from that commit and copying the same files produces no diff. The fix should detect this before attempting git operations and instead update the manifest directly.

## Decisions

- **Early exit before branch creation** — when `_find_base_commit` returns distance=0, skip the entire branch/commit/merge flow and go straight to manifest update. *Rejected: late recovery after `git commit` fails (fragile, leaves stale merge branch to clean up).*
- **Baseline records the exact-match commit, not latest** — the installed files are byte-identical to commit X, so that's what the baseline should say. If the source has newer commits, `status` shows "outdated" and the user runs `update`. *Rejected: setting baseline to latest commit on pinned branch (dishonest — claims sync to content the user hasn't seen).*
- **Two distinct messages, no duplicate hash** — since `_resolve_base_commit` already prints `Base commit: <hash> (exact match)`, the early-exit message should not repeat the hash. Scenario A (exact match is latest): skill is tracked, already up to date. Scenario B (source has newer commits): skill is tracked, suggest `skills update`.
- **`_resolve_base_commit` returns `_BestCommit | None`** instead of `str | None` — the caller needs the distance to detect exact match. Reuse `_BestCommit` as-is (keep underscore name, all module-private). *Rejected: adding a separate boolean return value (parallel signal for same concept).*
- **Only handle distance=0 path** — the existing noop check (line 187, `installed.match_files`) already covers skills with a baseline. The new code only catches the case that slips through (mergeable/untracked skills with `baseline=None`).
- **No file copying on early exit** — provider files already match the exact-match commit. No need to copy from source.
- **No special detached-skill handling** — `register_skill` with a fresh `Baseline` and `detached=False` (default) clears the flag automatically.
- **No extra reachability check** — `git log` runs on HEAD, which is the pinned branch (ensured by `_merge_start`), so returned commits are always reachable.

## Open questions

None — all questions resolved during grill.

## Out of scope

- Changing the existing noop check for skills with baselines.
- Handling non-zero distance edge cases differently.
- Modifying the `update` command behavior.

## Subtasks

- [x] [s08t1701](s08t1701-change-resolvebasecommit-to-return-bestcommit.md): Change `_resolve_base_commit` to return `_BestCommit | None`
- [x] [s08t1702](s08t1702-early-exit-on-exact-match.md): Early exit on exact match with manifest update
