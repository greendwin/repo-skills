---
id: s02
slug: rework-repo-workflow
status: pending
---

# Rework repo workflow

Lets this tool execute always from inside repo.

1. `skills init` - init current git-based repo to work as skills source.
TBD: what skills structure? if many skills we need to support subfolders to orgranize them.
Manifest must be stored inside repo -- multiple such repos can be used simultaneously.

2. `skills status` - show the same as `list` now, but with more details on actual state -- don't 'git pull', but check statuses for each skill either installed or orphaned; if installed - show whether it in sync or need to be 'merged', or 'outdated' (in case of match with original commit and neww updates); TBD - should we need additional state for 'conflict' (actually the same merge, but with rebase process).

3. `skills merge` - should work as peek to adopt new skills that are not in repo; in case of normal flow -- either copy new changes, or create merge branch and initiate rebase; if skill does not have meta info - we should perform search in history and peak closest version as a merge base.

4. `skills peek` - don't need in favor of `merge`; then only special here is that skill location when creating in rpo can be altered in case of subdirs -- we should ask user if repo is not in flat structure

5. repo structure is TBD - do we have 'skills' subfolder or flat right in repo? any other dirs? w should counfigure it on `init`

6. `skills update` - perform `git pull` and try to update all installed skills as currently implemented.
