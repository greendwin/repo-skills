---
id: s06t25
slug: support-skills-dependencies
status: pending
---

# Support skills dependencies

Many skills are dependent to each other (e.g. dev-loop -> setup-dev-loop, tdd; grill-with-docs -> to-tasks).

Lets support such dependencies declaration and use them on skill installation, so `skills install dev-loop` would install all dependant skills.

Deps declaration example (TBD):
```
skills depends <skill> <other1> <other2> ...   # skill -> other1, other2, ...
skills depends <skill> --list
skills depends <skill> --remove <other>

# alternatively:
skills depends add/remove/list ...
```
