---
id: s08t26
slug: misleading-already-synced-message
status: pending
---

# Misleading "already synced" message

Note "`is already synced`" is wrong, it _was_ detached, so we must tell that it was re-attached and now in-sync.

```
$ s update
...
Updating grill-with-docs ... up-to-date, detached (commit unreachable)
...

$ sl
Source agent-skills
  ...
  grill-with-docs                     claude  mergeable
  ...

$ smr grill-with-docs
grill-with-docs is already synced. Nothing to merge.
```

Trello: https://trello.com/c/ZCM2F600
