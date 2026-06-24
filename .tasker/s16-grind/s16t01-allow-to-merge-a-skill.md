---
id: s16t01
slug: allow-to-merge-a-skill
status: in-review
---

# Allow to merge a skill to *another* skill source

## Context

`skills merge <skill> --source X` does nothing useful for a *tracked* skill: `--source` currently only applies to orphan skills, and for a tracked skill `_merge_start` overwrites the target with `installed.source`, so the command reports sync state against the wrong source (`"already synced. Nothing to merge."`). Goal: let `merge --source X` write a tracked skill's current content into a *different* source X and, by default, retarget the skill to track X. See ADR `docs/adr/0006-single-source-retarget.md` and the **Tracking source** / **Retarget** glossary entries in `CONTEXT.md`.

## Decisions

- **Single-source retarget, not dual-tracking** — the manifest tracks exactly one source per skill. `merge --source X` (X≠Y) writes installed content into X and, by default, retargets the manifest to track X; "sync to both sources" stays a manual per-source merge. *Rejected: dual-source tracking (manifest stores a set; `update`/`status` reconcile across sources) — requires a schema change and an ambiguous "which source wins on divergence" answer the originating bug never needed.* (ADR 0006.)
- **Terminology** — adopt **Tracking source** (the single source a skill is tracked against = manifest `source`) and **Retarget** (changing it via `merge --source`). Keep **detached/reattach** strictly for the commit-reachability axis — do *not* reuse "attach" for source ownership. Opt-out flag is `--keep-source`. *Rejected: the task's `--no-attach`/"reattach" wording — collides with the existing Safe-reattach meaning.*
- **Base resolution always against X** — the Y-baseline commit is meaningless outside Y, so discard it for the cross-source merge. If X already has the skill → forced base search over X's history (existing `--search-base` machinery), then branch + merge (or `rebase_root` if no base). If X lacks the skill → orphan-add into X's `active_dir` (existing `_merge_orphan` flow). *Rejected: reusing `installed.baseline` against X — independent lineages, no shared base.*
- **Bypass the Y-baseline short-circuit when X≠Y** — gate the `_merge_start:177-181` / `_raise_in_sync` "already synced" check on `target_source == tracking_source`. For a cross-source merge, compute in-sync against **X**: if installed content byte-matches X's current skill commit → skip the write, go straight to the manifest step; else merge. This is the actual bug fix.
- **Has-skill provider resolution** — for a cross-source merge use `_find_skill_in_provider` (provider that *has* the skill; `--from` only if several; error if none), **not** `_resolve_diverged_provider` (Y-baseline-divergence based) — a skill unmodified vs Y must still be publishable to X.
- **Manifest semantics** — default (retarget): rewrite entry to `source=X`, `baseline=make_baseline(<X skill commit>, installed_path)`, `detached=False`. `--keep-source`: **no** manifest writes at all (must not run the normal `_finalize` baseline rewrite, or you'd get `source=Y` with an X-commit baseline). `--keep-source` only has meaning when X≠Y.
- **Messaging** — retarget: `Retargeted <skill>: now tracking <X> (was <Y>).`; `--keep-source`: `Merged <skill> into <X> (still tracking <Y>).`; in-sync-with-X retarget: `<skill> already matches <X> — now tracking <X> (was <Y>).` Update `--source` help to note it also merges/retargets a tracked skill. No interactive confirmation (the explicit flag is the intent).

## Edge cases

- `X == Y` (redundant `--source`): behaves exactly like today's same-source merge; `--keep-source` is ignored.
- X has no `skills_dir` configured and lacks the skill (orphan-add path): reuse the existing `active_dir is None` error.
- Skill unmodified vs Y but absent/different in X: still retargets/publishes (short-circuit bypass + has-skill provider resolution make this work).

## Key files

- `src/repo_skills/cli/_merge.py` — `merge` command (add `--keep-source`, extend `--source` semantics), `_merge_start` (target-source dispatch, bypass short-circuit, base-against-X, manifest rewrite vs keep-source), `_resolve_untracked` / `_merge_orphan` (orphan-add into X), `_find_skill_in_provider`, `_resolve_base_commit` (force search against X), `_finalize` (skip on `--keep-source`).
- `src/repo_skills/config/_skill_manifest.py` — `register_skill` for the retarget rewrite.
- `CONTEXT.md`, `docs/adr/0006-single-source-retarget.md` — already written.

## Acceptance criteria

- `merge <tracked-by-Y> --source X` where X already has the skill: content merged into X, manifest now `source=X`, success message names old/new source.
- Same where X lacks the skill: skill added to X's `active_dir` with a `feat: add` commit, manifest retargeted to X.
- `merge <tracked-by-Y> --source X --keep-source`: content lands in X, manifest still `source=Y` with its original baseline.
- `merge <synced-with-Y> --source X` (unmodified vs Y): still proceeds against X (no "already synced" short-circuit).
- `merge <tracked-by-Y> --source X` where installed already matches X's latest: no commit; manifest retargeted to X with the in-sync message.
- `merge <skill> --source Y` (== tracking source): unchanged legacy behavior.

## Open questions

- None. (Bidirectional/automatic dual-sync deferred — see Out of scope.)

## Out of scope

- Dual-source tracking / automatic two-way sync (separate feature, own schema + ADR).
- Changing orphan-skill `--source` behavior beyond unifying it under "the source to merge into".
