---
id: s08t05
slug: add-force-to-source-remove
status: pending
---

# Add --force to `source remove` (orphan installed skills)

`_source.py` (`source remove`):
> TODO: support --force option to do this

Add a `--force` flag to `source remove`. When used, remove skills from the manifest but leave files in place (they become orphan skills). Without --force, keep current behavior (refuse if skills are installed). Remove the TODO once fixed.
