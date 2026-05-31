---
id: s01t0401
slug: extract-shared-helpers-from-mergepy
status: in-review
---

# Extract shared helpers from _merge.py

**Goal:** Move `_find_in_provider` and `_resolve_untracked` to a shared module; update `_merge.py` imports. No new functionality — refactor only, existing merge tests must pass.

**Decisions:** Extract shared helpers to avoid cross-command imports.

**Key files:** `src/repo_skills/cli/_merge.py`, `src/repo_skills/cli/_utils.py`, `tests/cli/test_merge.py`
