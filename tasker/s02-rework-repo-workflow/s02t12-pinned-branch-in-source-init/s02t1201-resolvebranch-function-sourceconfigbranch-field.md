---
id: s02t1201
slug: resolvebranch-function-sourceconfigbranch-field
status: pending
---

# `resolve_branch` function + `SourceConfig.branch` field

**Goal:** Add `branch: str = ""` to `SourceConfig` and a free function `resolve_branch(config, git)` that falls back to `get_main_branch()` when empty.

**Decisions:**
- `branch: str = ""` default — existing `source.json` files work without migration
- Free function `resolve_branch(config, git)` near `SourceConfig` — single place for fallback logic

**Key files:** `src/repo_skills/config.py`, tests
