---
id: s08t23
slug: bad-skills-directory-detection-on
status: pending
---

# Bad skills directory detection on `source init`

```
$ skills source init
Initialized source my-skills.

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
```

# Issue #1: new source not in the list – should be shown all the time (print no skills)

# Issue #2: 'skills' directory was detected incorrectly

```
$ jq . source.json
{
  "name": "my-skills",
  "skills_dir": "skills",
  "branch": "main"
}
```

Repo layout has skills under `claude/skills/...` (and `copilot/...`), plus an empty top-level `skills/` dir which was wrongly detected as the skills dir.

Note: skills can be in multiple directories (in theory, first dir can be used as active on merging orphan skills), user should be able to provide list of dirs.

Main problem: tool should _never_ assume empty dir if there are existing skills in the repo. If common dir is the repo root (like here) then user should provide _list_ of dirs manually.

Trello: https://trello.com/c/laZPnXOc
