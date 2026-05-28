---
id: s08t04
slug: remove-mergeinprogress-blocking-check
status: pending
---

# Remove merge-in-progress blocking check

_merge.py:158 — Remove the check that blocks starting a new merge when a `skill-merge/*` branch already exists. Multiple merges can coexist; `_detect_merge_branch` already handles disambiguation for --continue/--abort.
