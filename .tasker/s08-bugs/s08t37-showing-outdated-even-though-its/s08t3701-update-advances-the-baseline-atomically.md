---
id: s08t3701
slug: update-advances-the-baseline-atomically
status: in-review
---

# Update advances the baseline atomically on content-sync

## Goal

After `skills update`, a skill that reaches content-sync has its `baseline.commit` advanced to the latest verified source commit on the pinned branch (alongside its file hashes), so a subsequent `skills status` no longer reports it as `outdated`. A locally-modified (`skipped`) skill leaves its baseline entirely untouched and continues to show `modified, outdated`. This fixes the reported bug end-to-end — `update` and `status` agree on "up-to-date".

## Decisions & constraints

- **Fix `update`, keep `status`'s commit-based model.** The baseline is a snapshot of the source at the last sync; `update` already refreshes the file-hash half, so it must refresh the commit half too. The whole bug is that `_run_updates` rebuilds the baseline with `commit=entry.baseline.commit` (stale) while refreshing `files`. *Rejected: switching `status` to content-based comparison — reverses the explicit commit-based decision from s08t16 and leaves the baseline commit permanently meaningless after the first update.*

- **Advance the whole baseline atomically, only on content-sync.** When an install reaches content-sync — any non-`skipped` outcome: already up-to-date, overwritten-because-unmodified, or freshly installed — refresh the entire baseline together: `commit = latest verified commit on pinned branch`, `files = source hashes`, and clear `detached`. When `skipped` (locally modified), leave the baseline entirely untouched (old commit AND old hashes — note this changes today's behavior of unconditionally refreshing `files` on skip). *Rejected: advancing the commit for skipped/modified skills — would hide that the source moved on under local changes.*

- **Recovery folds into the in-sync branch.** The unified advance rule subsumes the old `is_ancestor`-based recovery branch: an in-sync formerly-detached skill clears `detached` and advances in one step, and is never left outdated.

- **Detached *detection* moves to the skipped path.** Only a modified (`skipped`) skill can still hold a baseline commit that fell off history; in-sync skills always advance to a fresh reachable commit. Run the `is_ancestor(baseline.commit, pinned)` newly-detached check (mark `detached = True` when not reachable and not already detached) on the skipped path. This is the algorithm's steps 1–2 plus the atomic-advance rule. (Safe-reattach — steps 3–4 — is the next slice; this slice keeps the no-match case routed to the existing skip/merge behavior.)

## Edge cases

- `skipped` skill whose `baseline.commit` is still reachable → baseline untouched, not newly-detached, shown `modified, outdated`.
- `skipped` skill whose `baseline.commit` fell off history → marked `detached` (reported `untracked (need merge)`).
- Formerly-`detached` skill that is unmodified and whose source advanced → overwritten to latest, baseline advanced, `detached` cleared in one update.
- Fresh install (`dst` absent) counts as content-sync → baseline advanced.
- Latest verified commit unresolvable (e.g. `resolve_verified_commit` returns `None`, or source not in `source_branches` for `--offline`) → do not advance the commit; keep prior behavior rather than writing an empty/bogus commit.
- Multi-provider where one provider is `skipped` and another in sync → treat as not-in-sync (any `skipped` ⇒ baseline untouched).

## Key files

- `src/repo_skills/cli/_update.py` — `_update_skill`, `_run_updates`, `_SkillReport`, `_print_skill_report`; baseline construction at lines ~228-233 and the detached/recovered block at ~285-306.
- `src/repo_skills/git.py` — `resolve_verified_commit`, `get_skill_commit`, `is_ancestor` (already available).
- `src/repo_skills/cli/_status.py` — `_compute_outdated` (unchanged; used to assert agreement).
- `src/repo_skills/config/_skill_manifest.py` — `Baseline`, `register_skill`, `match_files`.
- `tests/cli/helper.py` — `FakeGitRepo` (commits, `is_ancestor`, `get_skill_commit`); existing update tests that assert `files` refresh on skip will need updating.

## Acceptance criteria

- Updating a skill whose source commit advanced (unmodified install) reports `updated` and a following `status` shows it `synced` (not `outdated`); the manifest `baseline.commit` equals the source's latest commit for the path.
- A skill already content-equal to source reports `up-to-date` and its `baseline.commit` is advanced to latest, so `status` no longer shows `outdated`.
- A locally-modified skill reports `skipped (modified)`, its baseline (commit and hashes) is unchanged, and `status` shows `modified, outdated`.
- A modified skill whose `baseline.commit` is unreachable from pinned is marked `detached`; an unmodified outdated skill is never marked detached.
- When the latest commit cannot be resolved, the commit is not advanced (no regression / no empty commit written).
