---
id: s08t20
slug: inconsistent-new-lines-between-groups
status: pending
---

# Inconsistent new lines between groups

```
Source agent-skills
  commit-summary                      claude  synced, outdated
  grill-me                            claude  synced
  grill-with-docs                     claude  synced, outdated
  tdd                                 claude  synced, outdated
  to-tasks                            claude  synced
  thermo-nuclear-code-quality-review          available
  todo-triage                                 available
Source my-skills
  bitbucket                           claude  mergeable
  code-reviewer                               available
  developer                                   available
  git-branch                                  available
  git-commit                                  available
  manager                                     available
  sentry                              claude  mergeable
  task-claim                                  available
  task-close                                  available
  team-lead                                   available

Untracked
  branch-summary                      claude  orphan
  diagnose                            claude  orphan
  improve-codebase-architecture       claude  orphan
  new-python-project                  claude  orphan
  test                                claude  orphan
  test2                               claude  orphan
  write-a-skill                       claude  orphan
  zoom-out                            claude  orphan
```

Need new line between sources, or no line before `Untracked`

Trello: https://trello.com/c/KQ0zCO61
