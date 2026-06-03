---
id: s06t17
slug: group-skills-when-installed-from
status: pending
---

# Group skills when installed from same source

Same `agent-skills` is duplicated three times.
Also all in green -- too much.
Somethings like
```
Installing skills from [g]agent-skills[/g]:
   * [b]dev-loop[/b]
   * [b]setup-dev-loop[/b]
```

Current output:

```
~ ⌚ 17:53:34
$ s install dev-loop setup-dev-loop setup-task-tracker
Installed dev-loop from agent-skills.
Installed setup-dev-loop from agent-skills.
Installed setup-task-tracker from agent-skills.
```
