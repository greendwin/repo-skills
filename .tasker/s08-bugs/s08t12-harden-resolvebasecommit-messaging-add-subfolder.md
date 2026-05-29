---
id: s08t12
slug: harden-resolvebasecommit-messaging-add-subfolder
status: done
---

# Harden _resolve_base_commit messaging + add subfolder test

All three TODOs live in `_merge.py` `_resolve_base_commit`; the "orphan branch" and "rework this message" ones edit the same echo block.

> TODO: in case of orphan branch we must tell this to
> (i.e. that rebase will be performed)

Announce to the user that a rebase will be performed when the resolved base commit lands on an orphan branch.

> TODO: rework this message

Fix the escape inconsistency: the exact-match branch escapes the commit message (`escape(r.message)`) while the distance branch passes `r.message` raw — an unescaped message can break rich-formatted output. Rework the base-commit message accordingly.

> TODO: test it when skill under category subfolder

Add a test for base-commit search when the skill sits under a category subdirectory (skills are identified by leaf name, but `rel_path` includes the category).

Remove each TODO once its fix lands.
