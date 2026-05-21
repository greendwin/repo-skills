---
id: s02t1202
slug: source-init-writes-current-branch
status: pending
---

# `source init` writes current branch + `--branch` flag

**Goal:** First init writes `git.current_branch()` to `branch` field. `--branch <name>` allows override (validated that branch exists locally). Reinit preserves existing pin unless `--branch` is explicitly passed.

**Decisions:**
- Init writes current branch explicitly via `git.current_branch()`
- `--branch <name>` for changing the pin — reuses idempotent reinit, no new subcommand
- Validates branch exists locally (catches typos at init time)
- Reinit preserves existing pin unless `--branch` is passed

**Key files:** `src/repo_skills/cli/_source.py`, `tests/cli/test_source_init.py`
