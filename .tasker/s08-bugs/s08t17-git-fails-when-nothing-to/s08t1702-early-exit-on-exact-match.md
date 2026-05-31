---
id: s08t1702
slug: early-exit-on-exact-match
status: done
---

# Early exit on exact match with manifest update

## Goal

When `_resolve_base_commit` returns distance=0, skip branch/commit/merge and update the manifest with a baseline pointing to the exact-match commit. Show the right message depending on whether the skill is already at the latest version or not.

## Decisions & constraints

- **Early exit before branch creation** — skip the entire branch/commit/merge flow and go straight to manifest update. *Rejected: late recovery after `git commit` fails (fragile, leaves stale merge branch).*
- **Baseline records exact-match commit, not latest** — the installed files are byte-identical to commit X, so that's what the baseline should say. If the source has newer commits, `status` shows "outdated" and the user runs `update`. *Rejected: setting baseline to latest commit on pinned branch (dishonest).*
- **Two distinct messages, no duplicate hash** — `_resolve_base_commit` already prints `Base commit: <hash> (exact match)`, so the early-exit message should not repeat the hash. Scenario A (exact match is latest): skill is tracked, already up to date. Scenario B (source has newer commits): skill is tracked, suggest `skills update`.
- **No file copying on early exit** — provider files already match the exact-match commit.
- **No special detached-skill handling** — `register_skill` with a fresh `Baseline` and `detached=False` (default) clears the flag automatically.
- The existing noop check (line 187, `installed.match_files`) is untouched. This new check goes after `_resolve_base_commit` returns.
- To determine "is latest", compare exact-match commit with `git.get_skill_commit(skill.rel_path)` on the current branch.

## Edge cases

- Exact match that IS the latest commit — no "outdated" hint, say "already up to date"
- Exact match on a previously-detached skill — detached flag should be cleared by `register_skill`

## Key files

- `src/repo_skills/cli/_merge.py` — `_merge_start`, after `_resolve_base_commit` call
- `tests/cli/test_merge.py` — new tests

## Acceptance criteria

- `skills merge` with exact-match base commit updates the manifest and exits without creating a branch or committing
- Manifest baseline has the exact-match commit and correct file hashes
- When exact match is latest commit: message says "already up to date"
- When source has newer commits: message suggests `skills update`
- No merge branch is created or left behind
- Previously-detached skill gets detached flag cleared
