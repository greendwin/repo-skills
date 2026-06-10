---
id: s08t37
slug: showing-outdated-even-though-its
status: pending
---

# Showing 'outdated' even though it's up-to-date

## Context

`skills update` reports skills as `up-to-date`, but a subsequent `skills status` reports the same skills as `outdated` — an inconsistency users hit on every routine update. Root cause: `update` refreshes a skill's baseline file hashes to the current source but preserves the stale baseline commit, while `status` detects outdated purely by comparing the baseline commit against the latest source commit for the skill's path. Once a skill's source commit advances, every `update` leaves the recorded commit stale, so `status` reports a fully-synced skill as `outdated` indefinitely. The goal is to make `update` and `status` agree on "up-to-date" by treating the baseline as a single atomic snapshot of the source (commit + file hashes) that advances together — while preserving the conservative "when in doubt, merge" stance for modified and history-diverged installs.

## Decisions

- **Fix `update`, keep `status`'s commit-based model** — the baseline is a snapshot of the source at the last sync; `update` already refreshes the file-hash half, so it must refresh the commit half too. *Rejected: switching `status` to content-based comparison (reverses the explicit commit-based decision in s08t16 and leaves the baseline commit permanently meaningless after the first update).*

- **Advance the whole baseline atomically, only on content-sync** — when an install reaches content-sync (any non-`skipped` outcome: already up-to-date, overwritten-because-unmodified, or freshly installed), refresh the entire baseline together: `commit = latest verified commit on pinned branch`, `files = source hashes`, and clear `detached`. A `skipped` (locally modified) install leaves the baseline entirely untouched (old commit, old hashes) → `status` shows `modified, outdated` → user resolves via `merge`. *Rejected: advancing the commit even for skipped/modified skills (would hide that the source moved on under local changes).*

- **Recovery = achieving content-sync, not commit reachability** — the unified advance rule subsumes the old `is_ancestor`-based recovery branch: a detached-but-unmodified skill overwrites to latest and reattaches in one step, and is never left outdated.

- **Per-skill detached/reattach algorithm** — with `reachable = is_ancestor(baseline.commit, pinned)`:
  1. `not detached and not reachable` → mark `detached = True`.
  2. `detached and reachable` → clear `detached`, run the normal update path.
  3. Still detached/untracked → **safe-reattach**: scan the pinned branch's history for the skill's path, newest→oldest, for a commit whose content is an exact full-content match to the *installed* copy; on match, re-pin the baseline to that commit (`commit = found`, `files = that content`, `detached = False`), then the normal path carries it to latest.
  4. No matching commit found → skip → manual `merge`.
  Safe-reattach distinguishes an *old-but-unmodified* install (content equals a real historical commit ⇒ safe to reattach and update) from a *genuinely modified* install (matches no commit ⇒ must merge) — a stronger test than comparing against the single recorded `baseline.files`.

- **Detached *detection* lives on the skipped path** — only a modified (`skipped`) skill can still hold a baseline commit that fell off history; in-sync skills always advance to a fresh reachable commit. The `is_ancestor` newly-detached check therefore runs for skills that are not brought into sync.

- **Safe-reattach search scope: full history, short-circuit on first match** — walk `log_commits(rel_path)` newest→oldest and stop at the first exact match. The pathological full-history cost is paid only in the no-match case (i.e. the modified/`merge` case); correctly classifying an ancient-but-unmodified install is worth more than bounding that rare worst case. *Rejected: a bounded window (would send a very old unmodified install to `merge` unnecessarily).*

- **Multi-provider: require provider agreement** — the manifest holds one baseline (one commit) per skill, so safe-reattach needs a single content fingerprint: only attempt it when all of a skill's installed copies are byte-identical; divergent copies are treated as modified → `merge`. *Rejected: matching per provider independently (would force splitting the one-baseline-per-skill manifest model).*

## Documentation captured

- `CONTEXT.md` — rewrote **Baseline** (now commit + per-file hashes, advanced atomically on content-sync), updated **Detached skill** (names both recovery paths), added **Safe-reattach**.
- `docs/adr/0002-detached-skill-handling.md` — amended with the safe-reattach recovery path, the baseline-advances-on-sync rule (and the original-bug explanation), the reachability-only-reattach rejected option, and the multi-provider constraint.

## Open questions

None.

## Out of scope

- Changing `skills status`'s commit-based outdated detection — the fix is entirely on the `update` side.
- Changing `skills merge` — modified / divergent / no-match installs continue to route to the existing merge flow unchanged.

## Subtasks

- [ ] [s08t3701](s08t3701-update-advances-the-baseline-atomically.md): Update advances the baseline atomically on content-sync
- [ ] [s08t3702](s08t3702-safereattach-by-content-search.md): Safe-reattach by content search
