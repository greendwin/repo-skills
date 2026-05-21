---
id: s06t07
slug: support-skills-merge-nocommit
status: pending
---

# Support 'skills merge --no-commit'

Sometimes we don't need auto-finalizing, and also want to revie by ourselves what was changed, since auto-apprive may not be valid.
So, if -n | --no-commit is provided -- find base commit, create merge branch, copy skill and let user do the rest (with hint to call merge --continue on finish).
