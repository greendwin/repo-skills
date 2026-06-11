---
id: s06t24
slug: source-remove-show-list-of
status: pending
---

# 'source remove': show list of skills in a bullet list

Example:
```
$ skills source remove agent-skills --force
Unregistered 10 skill(s): commit-summary, dev-loop, grill-me, grill-with-docs, new-python-project, 
setup-dev-loop, setup-task-tracker, tdd, to-tasks, todo-triage.
Removed source agent-skills at /home/greendwin/agent-skills.
```

Would be better:
```
$ skills source remove agent-skills --force
Unregistered 10 skill(s):
  * commit-summary
  * dev-loop
  * grill-me
  ...
Removed source agent-skills at /home/greendwin/agent-skills.
```
