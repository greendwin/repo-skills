---
id: s01t0403
slug: wire-git-validation-into-update
status: done
---

# Wire git validation into `update`

**Goal:** Remove `--commit` from update. Add `--offline` flag. Same validation as install. When files match and no manifest entry → add entry with auto-detected commit. When files differ → conflict.
**Decisions:** Never silently overwrite; auto-detect commit; caller controls pull; same validation
**Key files:** `src/skill_cli/main.py`, `tests/test_update.py`
