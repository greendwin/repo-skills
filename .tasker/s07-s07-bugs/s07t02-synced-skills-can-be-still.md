---
id: s07t02
slug: synced-skills-can-be-still
status: pending
---

# Synced skills can be still broken

Example:
```
$ skills status
Source agent-skills
  commit-summary                 claude  synced
  test                           claude  synced
  test2                          claude  synced
  grill-me                       available
  tdd                            available
```

Skills aree installed and told to be in sync, but their commits are actually not in pined branch!
Status is light-weighted, so it ok for it, but `skills update` should invalidate this state
report that commits are invalid and convert this skills to untracked (TBD).
