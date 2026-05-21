---
id: s02t1203
slug: remove-anybranch-wire-validaterepo-to
status: done
---

# Remove `--any-branch`, wire `_validate_repo` to pinned branch

**Goal:** Change `_validate_repo(git, branch: str)` signature. Remove `--any-branch` from `install` and `update`. Callers pass `resolve_branch()` result. Error message includes copy-pasteable `source init --branch <current>` hint.

**Decisions:**
- `_validate_repo(git, branch: str)` — caller passes resolved branch string
- Remove `--any-branch` from both `install` and `update` — no deprecation
- Install/update validate-only, no auto-checkout
- Error message: `"Not on the pinned branch (on '<current>', expected '<pinned>').\n  Use source init --branch <current> to change the pin."`

**Key files:** `src/repo_skills/cli/_install.py`, `src/repo_skills/cli/_update.py`, `tests/cli/test_install.py`, `tests/cli/test_update.py`
