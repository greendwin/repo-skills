---
id: s08t15
slug: wrong-base-commit-is-taken
status: done
---

# Wrong base commit is taken

## Context

`_find_base_commit` uses `installed.files` (manifest hashes) to match commits, but these hashes can be wrong — e.g. when a mergeable skill is first registered, hashes are taken from the source repo's latest commit, not from the installed copy. This causes false "exact match" results against the wrong commit. The root fix is twofold: (1) `_find_base_commit` should use real files from `installed_path` instead of manifest hashes, and (2) the manifest entry structure should bundle `commit` and `files` into a nested `Baseline` object so they can't get out of sync.

## Decisions

- **Introduce `Baseline` dataclass** — `commit: str` + `files: dict[str, str]`, stored as `baseline: Baseline | None` on `InstalledSkill`. Makes the invariant unrepresentable: either both commit and hashes are present, or neither. *Rejected: keeping flat fields with validation (doesn't prevent invalid states at the type level).*
- **Name it `baseline`** — matches the existing glossary term "Baseline hashes." *Rejected: `snapshot` (introduces a new term).*
- **Keep `detached` as a separate flag** — reachability checks require git access, which isn't always available when loading the manifest. *Rejected: deriving detached state at runtime (couples manifest reads to git operations).*
- **Baseline hashes always come from the source repo**, never from the installed copy. The baseline represents "what the source looked like at this commit." The installed copy may have user edits.
- **Mergeable skills register with `baseline=None`** — fixes the TODO at line 172. We don't know what commit the installed copy came from, so there's no valid baseline. *Rejected: hashing installed copy (records potentially dirty state as baseline); hashing source latest (pretends installed matches latest when it might not).*
- **`_find_base_commit` drops `installed` param** — uses `compute_file_hashes(installed_path)` for file list and comparison instead of manifest hashes.
- **`_compute_distance` takes `file_paths: set[str]`** instead of `InstalledSkill`. *Rejected: passing full hash dict (only keys are used).*
- **`_resolve_diverged_provider`**: when `baseline` is `None`, treat all providers with the skill on disk as diverged.
- **Early-out checks skip when `baseline` is `None`** — applies to "already synced" check and "nothing to merge" check in `_finalize`. Without a baseline, we can't claim nothing changed.
- **`_check_divergence` in status**: skip divergence label when `baseline` is `None` — the skill will already show as mergeable/untracked via other logic.
- **Manifest version field** — add `version: int`, matching `_provider_registry.py` pattern. Older versions get dropped (treated as empty manifest), not migrated.
- **Source rename** (`_source.py`) — passes `baseline=entry.baseline` through unchanged.

## Open questions

None — all branches resolved.

## Out of scope

- Reworking how `_reattach_installed_skill` decides *when* to reattach (current trigger logic is fine, just needs new param).
- Changes to `skills install` flow (separate from merge).

## Subtasks

- [x] [s08t1501](s08t1501-fix-findbasecommit-to-use-real.md): Fix _find_base_commit to use real files from disk
- [x] [s08t1502](s08t1502-introduce-baseline-dataclass-and-migrate.md): Introduce Baseline dataclass and migrate all access sites
