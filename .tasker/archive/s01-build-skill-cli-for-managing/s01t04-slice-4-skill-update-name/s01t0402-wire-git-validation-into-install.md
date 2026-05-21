---
id: s01t0402
slug: wire-git-validation-into-install
status: done
---

# Wire git validation into `install`

**Goal:** Remove `--commit` from install. Add `--offline` flag. Before copying: validate main branch, optionally pull, check clean, auto-detect commit, verify content matches. Inject git dependency via `Depends`.
**Decisions:** Remove `--commit`; shared repo validation; pull before install; dirty = stop; must be on main
**Key files:** `src/skill_cli/main.py`, `tests/test_install.py`
