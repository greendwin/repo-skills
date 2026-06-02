---
id: s08t21
slug: updating-concrete-skill-should-pull
status: pending
---

# Updating concrete skill should pull only its source

```
$ skills status
Source agent-skills
  commit-summary                 claude  synced, outdated
  grill-me                       claude  synced
  tdd                            claude  synced, outdated
  to-tasks                       claude  synced
  grill-with-docs                claude  mergeable
  new-python-project             claude  mergeable
  todo-triage                            available
Source my-skills
  sentry                         claude  synced
  bitbucket                      claude  mergeable
  branch-summary                 claude  mergeable

$ skills update commit-summary
Pulling agent-skills ... done
done
Updating commit-summary ... up-to-date
```

Note that `commit-summary` belongs to `agent-skills` and `my-skills` should not be pulled.

Trello: https://trello.com/c/yCMHR2BH
