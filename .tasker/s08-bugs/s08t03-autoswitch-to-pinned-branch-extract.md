---
id: s08t03
slug: autoswitch-to-pinned-branch-extract
status: pending
---

# Auto-switch to pinned branch (extract ensure_on_branch helper)

_install.py:178-180 — Extract a shared helper `ensure_on_branch(git, branch)` that asserts clean + auto-switches silently. Use it in install and merge modules, replacing the current error-on-wrong-branch behavior in install.
