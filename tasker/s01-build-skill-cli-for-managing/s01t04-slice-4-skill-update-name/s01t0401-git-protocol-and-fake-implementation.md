---
id: s01t0401
slug: git-protocol-and-fake-implementation
status: done
---

# Git protocol + wire into `install`

**Goal:** Define `GitRepo` protocol in `_git.py`, implement `FakeGitRepo` for tests, and wire git validation into the `install` command. Remove `--commit` from install. Add `--offline` flag. Before copying: validate main branch, optionally pull, check clean, auto-detect commit, verify content matches.
**Decisions:** New `_git.py` module behind a protocol; fake in CLI tests; remove `--commit`; shared repo validation; pull before install; dirty = stop; must be on main
**Key files:** `src/skill_cli/_git.py`, `src/skill_cli/main.py`, `tests/test_install.py`, `tests/helper.py`
