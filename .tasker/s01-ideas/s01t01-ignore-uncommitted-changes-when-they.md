---
id: s01t01
slug: ignore-uncommitted-changes-when-they
status: pending
---

# Ignore uncommitted changes when they do not relate to skills

```
$ skills update --offline
Pulling agent-skills ... skipped
Pulling my-skills ...
Error: Repo has uncommitted changes.
  repo: /home/greendwin/my-skills
```

Uncommitted changes outside of the skills dirs should not block update.

Trello: https://trello.com/c/DL7hSNKE
