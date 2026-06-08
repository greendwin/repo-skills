---
id: s10t0201
slug: remove-unused-commands
status: done
---

# Remove unused commands

**Goal:** Remove `peek` and `merge` stubs (unimplemented), remove `list` command (replaced by `status` later). Clean slate for new commands.
**Decisions:** `list` replaced by `status`, `peek` dropped in favor of `merge`.
**Key files:** `src/repo_skills/main.py`, `tests/test_list.py`, `tests/test_cli.py`
