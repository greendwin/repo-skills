---
id: s08t38
slug: unclear-error-on-install-failure
status: pending
---

# Unclear error on install failure

Note also that 'install' command must be idempotent -- don't stop if already installed (just warning, that --force is required to reinstall)
Validate also skill names before installation, so all errors would be before real installation.

```
# greendwin @ LAPTOP-C4SLVRPI in ~/agent-skills on git:main o [12:39:11] C:1
$ s install grill-me grill-with-docs setup-dev-loop setup-task-tracker tdd thermo-nuclear-code-quality-review to-tasks todo-triage
Installed grill-me from agent-skills.
Installed grill-with-docs from agent-skills.
Installed setup-dev-loop from agent-skills.
Installed setup-task-tracker from agent-skills.
Installed tdd from agent-skills.
Error: Multiple sources registered (agent-skills, my-skills).   <-- did not tell, what skill has multiple source

Use --source to specify.    <-- need better tip
```
