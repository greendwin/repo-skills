---
id: s06t18
slug: update-specific-source
status: pending
---

# Update specific source

Need `-s | --source` option for `skills update` to update only specific stream.

```
$ skills update -s agent-skills
Error: No such option: -s

$ skills update --source agent-skills
Error: No such option: --source

$ skills update commit-summary
Pulling agent-skills ... done
done
Updating commit-summary ... up-to-date
```

Trello: https://trello.com/c/kgwhW8is
