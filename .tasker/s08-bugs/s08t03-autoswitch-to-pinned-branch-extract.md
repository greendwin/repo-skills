---
id: s08t03
slug: autoswitch-to-pinned-branch-extract
status: done
---

# Auto-switch to pinned branch (extract ensure_on_branch helper)

`_install.py`:
> TODO: lets switch automatically if it's clean
> TODO: merge this code with others that check current_branch and ...

`_merge.py`:
> TODO: unify this switching logic with other commands

Extract a shared helper `ensure_on_branch(git, branch)` that asserts clean + auto-switches silently. Use it in the install and merge modules, replacing the current error-on-wrong-branch behavior in install. Remove the TODOs once fixed.
