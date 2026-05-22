---
id: s06t08
slug: use-merge-instead-of-rebase
status: pending
---

# Use merge instead of rebase on 'skills merge'

## Decisions

- **Merge as default strategy** — makes the merge base visible in git history; users can rebase manually if preferred
- **`--rebase` flag preserves old behavior** — opt-in for users who want linear history
- **Orphan branches always rebase** — no meaningful merge base to display, and `--allow-unrelated-histories` would confuse users
- **Three new `GitRepo` protocol methods** — `merge(branch) -> bool`, `is_merging() -> bool`, `merge_abort() -> None`; no `merge_continue` needed since `commit_all` with explicit message handles it
- **`_finalize` receives `already_merged` flag** — skips `checkout` + `fast_forward` when True, keeps single finalization path
- **`--continue`/`--abort` detect both states** — check `is_rebasing()` and `is_merging()`, handle whichever is active
- **`--continue` defaults to merge** when no conflict state is active (e.g. after `--no-commit`)
- **Commit messages unchanged** — temp branch commit stays as-is; merge commit uses git's default message

## Subtasks

- [ ] [s06t0801](s06t0801-add-merge-methods-to-gitrepo.md): Add merge methods to GitRepo protocol and implementations
- [ ] [s06t0802](s06t0802-switch-mergestart-to-use-merge.md): Switch _merge_start to use merge by default
- [ ] [s06t0803](s06t0803-add-rebase-flag.md): Add --rebase flag
- [ ] [s06t0804](s06t0804-update-continue-and-abort-to.md): Update --continue and --abort to handle both states
