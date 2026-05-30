---
id: s06t13
slug: allow-to-omit-skill-name
status: pending
---

# Allow to omit skill name when only one skill is modified

```
~/repo-skills on  main! ⌚ 16:32:50               
$ skills status                                    
Source agent-skills                                
  grill-me         claude  modified                
  commit-summary   mergeable  (untracked in claude)
  grill-with-docs  mergeable  (untracked in claude)
  tdd              mergeable  (untracked in claude)
  to-tasks         mergeable  (untracked in claude)
                                                   
Untracked                                          
  caveman          claude  orphan                  
  impl-loop        claude  orphan                  
  todo-triage      claude  orphan                  
  worktree-loop    claude  orphan                  
                                                   
~/repo-skills on  main! ⌚ 16:33:10               
$ skills merge -n                                  
Error: Skill name is required.                     
                                                   
Use --continue to finalize a merge in progress.    
```

In this scenario we can auto-detect skill name.
