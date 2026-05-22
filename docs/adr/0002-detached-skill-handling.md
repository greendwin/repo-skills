# Detached skills preserve manifest entries

When `skills update` discovers that an installed skill's commit is no longer reachable from the pinned branch, it marks the manifest entry as `detached` rather than removing it. This preserves the stored commit hash and baseline file hashes so that tracking can resume automatically if the commit becomes reachable again (e.g. after undoing a force-push or switching the pinned branch back).

## Considered Options

- **Remove the manifest entry.** Simpler, but loses the commit and baseline hashes permanently. The user would need to `install --force` to re-establish tracking, and the merge base history is gone.
- **Preserve with a `detached` flag.** Slightly more complex, but enables auto-recovery on the next `update` when the commit reappears on the pinned branch. Status displays detached skills as mergeable/orphan — no new UI concept needed.

## Consequences

- `skills merge` checks commit reachability in three tiers: reachable from pinned branch (proceed), reachable from another branch (stop, suggest `--search-base`), fully dangling (auto-search for base commit). This prevents merging unrelated history from other branches.
- Detached skills remain functional in the provider — installed files are never deleted without explicit user action.
