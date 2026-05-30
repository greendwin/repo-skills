---
id: s08t1501
slug: fix-findbasecommit-to-use-real
status: done
---

# Fix _find_base_commit to use real files from disk

## Goal

`_find_base_commit` and `_compute_distance` use `compute_file_hashes(installed_path)` instead of manifest hashes. This is the actual bug fix — matching is based on real disk files, not potentially stale/wrong manifest data.

## Decisions & Constraints

- Drop `installed: InstalledSkill` param from `_find_base_commit` — the function already receives `installed_path: Path`
- Compute `installed_hashes = compute_file_hashes(installed_path)` once at the top of `_find_base_commit`, use its keys as file list and values for exact-match comparison
- `_compute_distance` takes `file_paths: set[str]` instead of `InstalledSkill` — only keys are needed, not hashes
- Call site at `_resolve_base_commit` (line 472) stops passing `installed`
- The staged diff already removed `installed` from the signature but the body still references it — complete this fix

## Key files

- `src/repo_skills/cli/_merge.py` — `_find_base_commit`, `_compute_distance`, `_resolve_base_commit`
- `tests/cli/test_merge.py`

## Acceptance criteria

- `_find_base_commit` signature: `(git, skill_rel, installed_path)` — no `InstalledSkill`
- `_compute_distance` signature: `(git, commit, skill_rel, file_paths, installed_path)` — no `InstalledSkill`
- File list and hashes for comparison come from `compute_file_hashes(installed_path)`
- `tox` green
