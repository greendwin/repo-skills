---
id: s06t14
slug: inconsistent-status-command
status: pending
---

# Inconsistent 'status' command -

Note two different styles for untracked labels, they should be consistent

```
~/repo-skills on  main! ⌚ 0:00:25                
$ skills status                                    
Source agent-skills                                
  grill-me         claude  untracked               
  commit-summary   mergeable  (untracked in claude)
  grill-with-docs  mergeable  (untracked in claude)
  tdd              mergeable  (untracked in claude)
  to-tasks         mergeable  (untracked in claude)
                                                   
Untracked                                          
  caveman          claude  orphan                  
  impl-loop        claude  orphan                  
  todo-triage      claude  orphan                  
  worktree-loop    claude  orphan                  
```
