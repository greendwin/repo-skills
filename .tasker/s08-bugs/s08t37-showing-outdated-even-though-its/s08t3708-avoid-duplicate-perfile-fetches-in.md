---
id: s08t3708
slug: avoid-duplicate-perfile-fetches-in
status: done
---

# Avoid duplicate per-file fetches in merge base search

## Rationale

For each of up to `_MAX_SEARCH_COMMITS` (50) commits, `_find_base_commit` in `src/repo_skills/cli/_merge.py` now calls `git.commit_content_hashes` (a full `ls-tree -r` + `cat-file --batch` over the whole skill tree) AND, on no exact match, re-fetches every installed file via `get_file_at_commit` plus `_compute_distance` (which fetches each file again). RealGitRepo does up to three separate git subprocess passes per non-matching commit. For deep history this is a measurable regression vs the previous single-pass approach.

## Suggested fix

Fetch the commit's content hashes once via `commit_content_hashes` and reuse them: if it equals `installed_hashes`, exact match; otherwise derive the missing-file disqualification and the distance inputs from the already-fetched data instead of re-reading blobs. Alternatively, only call `commit_content_hashes` when the cheaper per-file subset already matches, since a full-tree match implies the subset matches.
