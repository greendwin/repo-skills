---
id: s08t41
slug: relax-clean-repo-check-to
status: pending
---

# Relax clean-repo check to ignore changes outside skill dirs

`src/repo_skills/cli/../git.py` · sync/checkout guard:
> TODO: it's ok if it's not clean outside skill dirs and this does
> not prevent us from changing branch

`_synced_repo` (git.py) refuses to proceed when `not git.is_clean()`, but uncommitted changes *outside* the tracked skill directories neither risk the skill files nor block a branch switch.

Fix: scope the cleanliness check to the skill directories (or otherwise permit a dirty tree outside them) so `require_clean`/checkout/pull only fail on dirt that actually matters. Remove the TODO once fixed.
