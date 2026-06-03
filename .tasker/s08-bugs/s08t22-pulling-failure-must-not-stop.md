---
id: s08t22
slug: pulling-failure-must-not-stop
status: pending
---

# Pulling failure must not stop update

```
$ skills update
Pulling agent-skills ... done
Pulling my-skills ...
Error: Repo has uncommitted changes.
  repo: /home/greendwin/my-skills
```

Don't stop update if it skippable (i.e. repo can be under password so pull will always fail, it should not be a problem)

Trello: https://trello.com/c/QWtXGrQr
