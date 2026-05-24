---
id: s07t0202
slug: searchbase-and-search-reporting
status: done
---

# --search-base and search reporting

## Goal

Add `--search-base` flag to `skills merge` that forces base commit search regardless of stored commit. Improve `_find_base_commit` to report what it found: commit hash, line distance, and first line of commit message.

## Decisions & Constraints

- **`--search-base` ignores `entry.commit` and searches git history.** Useful when stored commit is on a wrong branch or user wants to re-anchor. This flag is also suggested by the three-tier reachability check (slice 6).
- **Search reports commit hash + distance + first line of commit message.** Gives user enough context to judge if the found base is reasonable. *Rejected: per-file breakdown (available in the diff itself once merge starts).*
- **Needs a new git method to get commit message.** Something like `get_commit_message(commit) -> str` returning the first line. Add to GitRepo protocol.

## Key files

- `src/repo_skills/cli/_merge.py` — add `--search-base` CLI option, extend `_find_base_commit` reporting
- `src/repo_skills/git.py` — add commit message method to protocol
- `src/repo_skills/git_real.py` — implement commit message retrieval
- `tests/cli/helper.py` — FakeGitRepo support
- `tests/cli/test_merge.py` — tests

## Acceptance criteria

- `--search-base` ignores `entry.commit` and searches git history
- Search output includes commit hash, line distance, and first line of commit message
- Normal merge (without `--search-base`) still uses stored commit as before
