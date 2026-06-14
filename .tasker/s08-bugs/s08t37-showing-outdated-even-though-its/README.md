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

## Decisions — baseline invariant hardening

These refine the "advance atomically" decisions above by making the `Baseline(commit, files)` invariant non-negotiable. They supersede s08t3701's edge-case handling for an unresolvable commit ("keep prior behavior"), which copied files while leaving a stale/mismatched baseline — a half-applied update that breaks the invariant.

- **The baseline invariant is sacred** — `Baseline(commit, files)` must always satisfy: the skill's content at `commit` hashes exactly to `files`. A file copy may only be performed when a matching baseline can be constructed; we cannot refresh hashes without a commit, or a commit without matching hashes.

- **Resolve the verified commit before copying** — `_update_skill` resolves `latest_commit` up front, before the provider copy loop, so the side-effecting copy never runs unless a valid baseline is constructible. *Rejected: copying first then rolling back when the commit turns out unresolvable (fragile restore of files we should never have touched).*

- **Committed-but-dirty source → error** — when the source working tree matches no commit for the skill's path (uncommitted/extra/missing files) or no commit touches the path, this is an actionable per-skill error: `resolve_verified_commit` raises `AppError`, which in `update` propagates to the existing failed / `render_error` path, leaving files AND baseline untouched (skill not re-registered). *Rejected: silently keeping the old baseline after the copy (the original half-apply bug).*

- **Precise verification detail via a result object** — `verify_commit_content` returns a `CommitVerification` dataclass (`matches: bool`, `reason: str | None` display message, `file: str | None` offending file, `repo: str | None` plain repo path) instead of a bare `bool`. It reports only the FIRST offending file (`not present in commit` / `missing file` / `file differs` / `untracked file`) so the friendly message stays compact; the typed `file`/`repo` fields (plain values, no markup) are assembled into `AppError(props=...)` by the consuming caller. *Rejected: bare bool (no actionable detail); encoding ok/fail in a `str | None` (state in a primitive — the authoritative flag is `matches`); a `props: dict[str, str]` bag (untyped/stringly-keyed — typed fields are clearer and the caller builds the AppError props dict).*

- **`resolve_verified_commit` raises instead of returning `None`** — install and update both want the error; `_install._resolve_commit` simplifies to a direct call (its hand-built message removed). `_update_attach` keeps its intentional "try-or-skip" probe by catching the `AppError` and returning `None`, logging it via `console.debug_traceback()` so the reason still surfaces under `--debug`.

- **Source unavailable (pull failed) → skip, not error** — when a skill's source repo/branch is absent because `_pull_sources` hit a pull failure (already reported once at source level), short-circuit before the copy loop and report `skipped (source unavailable)` — never `up-to-date`, and never a redundant per-skill error. Files and baseline are left untouched (invariant-safe). *Rejected: a per-skill `AppError` for every skill of the failed source (N duplicate errors burying the one real cause).*

- **`_advance_baseline` simplification** — with resolve-before-copy plus the raise, the `in_sync and latest_commit is None` branch becomes unreachable; remove it.

## Documentation captured

- `CONTEXT.md` — rewrote **Baseline** (now commit + per-file hashes, advanced atomically on content-sync), updated **Detached skill** (names both recovery paths), added **Safe-reattach**.
- `docs/adr/0002-detached-skill-handling.md` — amended with the safe-reattach recovery path, the baseline-advances-on-sync rule (and the original-bug explanation), the reachability-only-reattach rejected option, and the multi-provider constraint.

## Open questions

None.

## Out of scope

- Changing `skills status`'s commit-based outdated detection — the fix is entirely on the `update` side.
- Changing `skills merge` — modified / divergent / no-match installs continue to route to the existing merge flow unchanged.
- Enumerating *all* offending files in a verification failure — only the first is reported (compact message); broaden later if too coarse.

## Subtasks

- [x] [s08t3701](s08t3701-update-advances-the-baseline-atomically.md): Update advances the baseline atomically on content-sync
- [x] [s08t3703](s08t3703-commitverification-result-object-pinpoints-the.md): CommitVerification result pinpoints the first content mismatch
- [x] [s08t3704](s08t3704-enforce-the-baseline-invariant-in.md): Enforce the baseline invariant in update and install
- [ ] [s08t3705](s08t3705-safereattach-by-content-search.md): Safe-reattach by content search
- [x] [s08t3706](s08t3706-remodel-skillreport-sourceunavailabledetached-as-a.md): Remodel _SkillReport source-unavailable/detached as a discriminated outcome
- [x] [s08t3707](s08t3707-extract-shared-skilldir-overwrite-primitive.md): Extract shared skill-dir overwrite primitive for update and install
