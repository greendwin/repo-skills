---
id: s06t16
slug: autoattach-untracked-skills-on-update
status: pending
---

# Auto-attach untracked skills on `update` when they match source exactly

When `update` runs, detect untracked skills (directories in provider install paths not in manifest) that have a source counterpart. If the installed copy's file hashes exactly match the source skill at its latest commit, silently register the skill in the manifest (attach it). Print a line like "Attached skill X (matched source Y)". Modified copies stay untouched.

`src/repo_skills/cli/_update.py`:
> TODO: can we do anything with skills that are not in manifest?

This is a non-destructive bookkeeping operation — no files are changed, only the manifest gains an entry. Reduces manual `install --force` steps for skills that are already in sync.

Remove the TODO once fixed.
