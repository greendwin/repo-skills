---
id: s08t07
slug: delete-resolvedstale-todo-comments
status: pending
---

# Delete resolved/stale TODO comments

Remove TODOs that are resolved or not actionable design questions:

`_merge.py` `_finalize`:
> TODO: if equal, then why do we copy?

— code is correct; `is_equal` drives the message only. Delete the comment.

`_source.py` (`source list`):
> TODO: test these branches on (missing) aand (not-inited)

— testing gap, not a design issue. Delete the comment here once the tests are added in s08t08.
