---
id: s08t17
slug: git-fails-when-nothing-to
status: pending
---

# Git fails when nothing to merge

```
~/repo-skills on  main! ⌚ 18:53:50                                          
$ skills merge grill-me
Base commit: 0b1ad452 (exact match)
Message: feat: vendor `grill-me`, `tdd`, and `commit-summary` skills
Error: Git command failed: git commit -m chore: merge `grill-me` from `claude`
  repo: /home/greendwin/agent-skills
  branch: skill-merge/claude/grill-me
On branch skill-merge/claude/grill-me nothing to commit, working tree clean
```

we should handle this correctly -- on exact match we should just update a manifest entry and sync this skill to latest version
