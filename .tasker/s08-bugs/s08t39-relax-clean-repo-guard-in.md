---
id: s08t39
slug: relax-clean-repo-guard-in
status: pending
---

# Relax clean-repo guard in ensure_on_branch for the no-checkout path

`ensure_on_branch` currently refuses to proceed when the *whole* repo is dirty, even when no branch switch is needed. Unrelated WIP elsewhere in the repo then blocks install/merge.

`src/repo_skills/git.py` · `ensure_on_branch`:
> TODO: it's ok if it's not clean outside skill dirs and this does
>       not prevent us from changing branch

Decision (from triage grill):
- When a checkout or pull is needed, `git checkout` touches the whole working tree → keep requiring the **whole repo clean** (unchanged, safe).
- When already on the target branch and no pull is requested (only `require_clean`), scope the clean-check to the **target skill's path** (e.g. `<source>/<rel_path>`), not the whole repo. Unrelated changes elsewhere don't block; use the repo as-is.

Implementation note: `ensure_on_branch` is generic and doesn't currently know the operated-on skill — pass the target path(s) in as a new argument to scope the clean-check. Remove the TODO once fixed.
