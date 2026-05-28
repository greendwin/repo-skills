---
id: s08t07
slug: delete-resolvedstale-todo-comments
status: pending
---

# Delete resolved/stale TODO comments

Remove TODOs that are resolved or not actionable design questions:
- _merge.py:529 "if equal, then why do we copy?" — code is correct, is_equal drives the message only
- _source.py:170 "test these branches" — testing gap, not a design issue (add tests when implementing)
