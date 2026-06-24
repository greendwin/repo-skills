---
id: s06t27
slug: auto-attach-an-explicitly-named
status: pending
---

# Auto-attach an explicitly-named, on-disk, uninstalled skill in update

`skills update <name>` where `<name>` is not in the manifest hard-errors, even though the no-filter `update` run already discovers attach candidates for untracked installs. The machinery exists; it's just gated off when a skill is named explicitly.

`src/repo_skills/cli/_update.py` · `_validate_filters`:
> TODO: we can target untracked skill to try to auto-attach it

Decision (from triage grill): when a named skill isn't in the manifest but *is present on disk* as an untracked install, route it through the existing attach-candidate path (`find_attach_candidates` / safe-reattach) instead of erroring. Keep the hard `Skill <name> is not installed` error only when nothing is on disk (genuine typo / nonexistent skill), so typos still get a crisp error. Remove the TODO once fixed.
