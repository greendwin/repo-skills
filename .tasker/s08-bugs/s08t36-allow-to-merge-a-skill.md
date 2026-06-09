---
id: s08t36
slug: allow-to-merge-a-skill
status: pending
---

# Allow to merge a skill to *another* skill source

When --source provided, we should use this source as a merge target (TBD: if there are conflicts with existing logic).
We should alse *attach* this skill to a *new* source (so multiple sources should be able to *store* the same skill, but only one could be currently attached).

TBD: how we can easily reattach a skill to another source (i.e. to sync between both of them), we also must control, whether we want to attach a skill to the new source (we can add --no-attach option? by default should re-attach).

```
# greendwin @ ecimbalyuk in ~/agent-skills on git:dev-loop o [13:54:24]
$ sl
Source agent-skills
  commit-summary                      claude  synced, outdated
  dev-loop                            claude  synced, outdated
  grill-me                            claude  synced
  grill-with-docs                     claude  synced, outdated
  new-python-project                  claude  synced
  setup-dev-loop                      claude  synced, outdated
  setup-task-tracker                  claude  synced, outdated
  tdd                                 claude  synced, outdated
  to-tasks                            claude  synced, outdated
  todo-triage                         claude  synced
Source my-skills
  bitbucket                           claude  modified
  branch-summary                      claude  synced
  impl-loop                           claude  synced
  sentry                              claude  modified
  thermo-nuclear-code-quality-review  claude  synced

Untracked
  diagnose                            claude  orphan
  improve-codebase-architecture       claude  orphan
  trello                              claude  orphan
  write-a-skill                       claude  orphan
  zoom-out                            claude  orphan

# greendwin @ ecimbalyuk in ~/agent-skills on git:dev-loop o [13:54:26]
$ skills merge thermo-nuclear-code-quality-review -s agent-skills
Enter passphrase for key '/home/greendwin/.ssh/id_ed25519':
thermo-nuclear-code-quality-review is already synced. Nothing to merge.
```
