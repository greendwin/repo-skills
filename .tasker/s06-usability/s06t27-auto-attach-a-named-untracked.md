---
id: s06t27
slug: auto-attach-a-named-untracked
status: pending
---

# Auto-attach a named untracked skill instead of erroring "not installed"

`src/repo_skills/cli/_update.py` · target-name validation:
> TODO: we can target untracked skill to try to auto-attach it

When `update -s <name>` names a skill that is not in the manifest, the command currently raises `Skill <name> is not installed.`. If an untracked-but-matching install exists on disk, it could be auto-attached instead (the explicitly-named counterpart to the scan-based auto-attach delivered in s06t16).

Fix: on the named-target path, attempt the same exact-hash attach s06t16 uses; only raise when no matching untracked install is found. Remove the TODO once fixed.
