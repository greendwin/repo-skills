# Detached skills preserve manifest entries

When `skills update` discovers that an installed skill's commit is no longer reachable from the pinned branch, it marks the manifest entry as `detached` rather than removing it. This preserves the stored commit hash and baseline file hashes so that tracking can resume automatically if the commit becomes reachable again (e.g. after undoing a force-push or switching the pinned branch back).

A detached entry can also recover when its commit does *not* reappear, via **safe-reattach**: `update` scans the pinned branch's history for the skill's path and, if some commit's content is an exact full-content match to the installed copy, re-pins the baseline to that commit. This distinguishes an *old-but-unmodified* install (its content equals a real historical commit ⇒ safe to reattach and update) from a *genuinely modified* install (matches no commit ⇒ must be resolved via `merge`) — a stronger test than comparing against the single recorded baseline.

Underpinning both paths, `update` advances the **whole** baseline (commit + per-file hashes) atomically, and only when the install reaches content-sync with the source. A locally modified (`skipped`) install leaves the baseline untouched. This is what keeps `skills update` and `skills status` agreeing on "up-to-date": before, `update` refreshed the baseline hashes but left the commit stale, so `status` reported a synced skill as `outdated` indefinitely.

## Considered Options

- **Remove the manifest entry.** Simpler, but loses the commit and baseline hashes permanently. The user would need to `install --force` to re-establish tracking, and the merge base history is gone.
- **Preserve with a `detached` flag.** Slightly more complex, but enables auto-recovery on the next `update` when the commit reappears on the pinned branch. Status displays detached skills as mergeable/orphan — no new UI concept needed.
- **Reattach only by commit reachability.** Recovers a restored force-push but cannot help when the commit is gone for good even though identical content still exists on the branch — such installs would be stuck as detached forever.
- **Safe-reattach by content search.** Walks the path's history newest→oldest and short-circuits on the first exact match. Worst-case (full-history) cost is paid only when there is no match — i.e. the modified/`merge` case — which is acceptable for correctly classifying old-unmodified installs.

## Consequences

- `skills merge` checks commit reachability in three tiers: reachable from pinned branch (proceed), reachable from another branch (stop, suggest `--search-base`), fully dangling (auto-search for base commit). This prevents merging unrelated history from other branches.
- Detached skills remain functional in the provider — installed files are never deleted without explicit user action.
- Safe-reattach requires a single content fingerprint: when a skill is installed under multiple providers, all installed copies must be byte-identical to attempt it; divergent copies are treated as modified and routed to `merge`.
