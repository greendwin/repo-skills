---
id: s08t3705
slug: safereattach-by-content-search
status: pending
---

# Safe-reattach by content search

## Goal

On `skills update`, a detached or untracked install whose content exactly matches some commit in the pinned branch's history is reattached to that commit (baseline re-pinned, `detached` cleared) and then carried up to latest by the normal update path. An install whose content matches no historical commit is correctly identified as a genuine modification and routed to `merge`. This is algorithm steps 3–4, built on top of s08t3701.

## Decisions & constraints

- **Safe-reattach by content search (new git capability — a deep module).** When a skill is still detached/untracked after the reachability checks, scan the pinned branch's history for the skill's path, newest→oldest, for a commit whose content is an **exact full-content match** to the *installed* copy. On the first match, re-pin the baseline (`commit = found commit`, `files = that content`, `detached = False`); the normal update path then carries it to latest. Expose this as a simple interface (e.g. find-first-matching-commit given the path and a target content fingerprint), encapsulating `log_commits` iteration + per-commit content hashing behind it. Note: the existing `verify_commit_content` compares a commit against the *source working dir*, not the installed copy — this slice needs to compare against the installed copy's hashes.

- **Why it matters.** Safe-reattach distinguishes an *old-but-unmodified* install (content equals a real historical commit ⇒ safe to reattach and update) from a *genuinely modified* install (matches no commit ⇒ must merge) — a stronger test than comparing against the single recorded `baseline.files`.

- **Search scope: full history, short-circuit on first match.** Walk `log_commits(rel_path)` newest→oldest and stop at the first exact match. The pathological full-history cost is paid only in the no-match case (the modified/`merge` case). *Rejected: a bounded window — would send a very old unmodified install to `merge` unnecessarily.*

- **Multi-provider: require provider agreement.** The manifest holds one baseline (one commit) per skill, so safe-reattach needs a single content fingerprint: only attempt it when all of a skill's installed copies are byte-identical; divergent copies are treated as modified → `merge`. *Rejected: matching per provider independently — would force splitting the one-baseline-per-skill manifest model.*

- **No match → skip → manual `merge`.** Preserve the conservative "when in doubt, merge" stance; never silently overwrite a divergent install.

## Edge cases

- Installed content matches the latest commit's content → trivially reattaches (degenerate exact match) and is already up-to-date.
- Installed content matches an old commit but not latest → reattach to the old commit, then normal path overwrites to latest and advances the baseline.
- Installed content matches no commit in history → no reattach, skip, `merge`.
- Multiple providers whose copies disagree → no single fingerprint → treat as modified, skip (do not search).
- Empty / missing history for the path (`log_commits` returns nothing) → no match → skip.
- Line-ending normalization must be consistent between the installed copy hashing and the committed content (mirror existing `normalize_line_endings` usage) so matches aren't missed.

## Key files

- `src/repo_skills/git.py` — `GitRepo` protocol: add the find-matching-commit capability (builds on `log_commits`, `get_file_at_commit`).
- `src/repo_skills/git_real.py` — real implementation (reuse `ls-tree`/`get_file_at_commit`/`normalize_line_endings` patterns from `verify_commit_content`).
- `tests/cli/helper.py` — `FakeGitRepo`: mirror the new capability over its in-memory commit/content model.
- `src/repo_skills/cli/_update.py` — wire steps 3–4 into `_update_skill` after the reachability handling from s08t3701; add the multi-provider agreement guard.
- `src/repo_skills/config/_utils.py` — `compute_file_hashes` (for the installed-copy fingerprint).

## Acceptance criteria

- A detached skill whose installed content exactly matches an older reachable commit is reattached (manifest `detached` cleared, `baseline.commit` set to the matched commit) and then updated to latest; `status` shows it `synced`.
- A skill whose installed content matches no commit on the pinned branch is left unmodified-on-disk, reported as needing `merge`, and not silently overwritten.
- The search stops at the first (newest) matching commit rather than scanning the whole history when a match exists.
- When two providers hold byte-different copies of the same skill, safe-reattach is not attempted and the skill is routed to `merge`.
- The new git method has direct unit coverage via `FakeGitRepo` (match found at head, match found deep, no match, empty history).
