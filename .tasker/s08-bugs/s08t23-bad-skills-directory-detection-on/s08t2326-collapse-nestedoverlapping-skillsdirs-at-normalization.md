---
id: s08t2326
slug: collapse-nestedoverlapping-skillsdirs-at-normalization
status: done
---

# Collapse nested/overlapping skills_dirs at normalization

## Context

`_collect_source_skills` (`src/repo_skills/config/_source.py`) iterates `skills_dirs` and runs an independent `os.walk` per entry. When two configured dirs overlap/nest (one is a prefix of another, e.g. `["claude", "claude/skills"]` or `["skills", "skills/group"]`), the shared subtree is walked twice.

The correctness symptom (a re-sighted skill being mis-reported as a collision and dropped) was already FIXED on s08t2304 by deduping identical `rel_path`s inside `_collect_source_skills`. What remains is the redundant traversal: the redundancy is created at normalization time but only patched at collection time — logic split across layers.

`_normalize_skills_dirs` (`src/repo_skills/cli/_source.py`) currently only exact-dedups via `dict.fromkeys`; it does not collapse nested entries. The helper `discovery.path_within` (lexical containment) is the right tool.

Deferred from the dev-loop on s08t2304 (refactor phase) because collapsing nested entries mutates the STORED `skills_dirs` (observable in the `dirs:` change line and `active_dir` semantics), so it is NOT behavior-preserving and needs its own review.

## Approach

- In `_normalize_skills_dirs`, after computing each `resolved`, skip it if it is contained within an already-accepted dir (and optionally drop already-accepted dirs it contains) using `path_within` on resolved absolute paths, before `rel_posix`.
- Preserve ordering so the active (first) dir wins.

## Decisions to make

- Whether to drop a nested entry silently or note it (consistent with `_note_empty_skills_dirs` style).
- Behavior of an already-stored `source.json` with nested dirs: normalization runs on `init`/`reinit`; decide whether to also collapse on load (probably not — `_collect_source_skills` already tolerates overlap defensively).

## Acceptance criteria

- `skills init`/reinit with overlapping `--skills-dir` values stores only the non-contained dirs; the subtree is walked at most once.
- The `dirs:` change line reflects the collapsed list.
- `_collect_source_skills`' defensive identical-path dedup still works for any overlap reaching it directly.
- `uv run tox` green.

## Out of scope

- Walker unification / dot-dir pruning policy (separate follow-up).
