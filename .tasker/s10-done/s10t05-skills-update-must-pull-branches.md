---
id: s10t05
slug: skills-update-must-pull-branches
status: pending
---

# `skills update` must pull branches and perform auto-attach even when no skills are installed

```
$ skills status
Source agent-skills
  commit-summary                 claude  mergeable
  grill-me                       claude  mergeable
  grill-with-docs                claude  mergeable
  tdd                            claude  mergeable
  to-tasks                       claude  mergeable

Untracked
  bitbucket                      claude  orphan
  ...

$ skills update
No skills installed.
```

Note that there are mergeable skills that could be auto-attached to existing skill.

(Related to s06t16 auto-attach-on-update, but distinct: this is the early-exit "No skills installed." path.)

Trello: https://trello.com/c/OD8WoIGL
