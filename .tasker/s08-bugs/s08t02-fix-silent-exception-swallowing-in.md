---
id: s08t02
slug: fix-silent-exception-swallowing-in
status: pending
---

# Fix silent exception swallowing in commit matching

_merge.py:449 — Broad `except Exception: continue` can cause false base-commit matches. Fix: catch only the specific "file not found at commit" error. Missing file disqualifies the candidate commit entirely. Any other exception propagates.
