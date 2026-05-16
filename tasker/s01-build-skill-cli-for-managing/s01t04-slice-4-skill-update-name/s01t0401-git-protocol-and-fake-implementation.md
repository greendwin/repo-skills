---
id: s01t0401
slug: git-protocol-and-fake-implementation
status: pending
---

# Git protocol and fake implementation

**Goal:** Define the `GitRepo` protocol in `_git.py` with methods: `pull()`, `get_skill_commit(skill_path)`, `is_clean(skill_path)`, `get_main_branch()`, `current_branch()`, `verify_commit_content(commit, skill_path)`. Implement a `FakeGitRepo` for tests.
**Decisions:** New `_git.py` module behind a protocol; fake in CLI tests
**Key files:** `src/skill_cli/_git.py`, `tests/helper.py`
