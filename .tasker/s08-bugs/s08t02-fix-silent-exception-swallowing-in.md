---
id: s08t02
slug: fix-silent-exception-swallowing-in
status: pending
---

# Fix silent exception swallowing in commit matching

`_merge.py` `_find_base_commit`:
> TODO: it's invalid to silently skip all exceptions
> we can wrongly match base commit

Broad `except Exception: continue` can cause false base-commit matches. Fix: catch only the specific "file not found at commit" error. A missing file disqualifies the candidate commit entirely. Any other exception propagates. Remove the TODO once fixed.
