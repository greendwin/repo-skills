---
id: s01t0404
slug: real-gitrepo-implementation
status: done
---

# Real `GitRepo` implementation

**Goal:** Implement the real `GitRepo` using `subprocess.run`. Integration tests with real temporary git repos.
**Decisions:** Protocol interface; real repos in integration tests
**Key files:** `src/skill_cli/_git.py`, `tests/test_git_integration.py`
