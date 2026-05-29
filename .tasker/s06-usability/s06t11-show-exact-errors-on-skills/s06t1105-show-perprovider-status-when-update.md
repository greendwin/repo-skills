---
id: s06t1105
slug: show-perprovider-status-when-update
status: pending
---

# Show per-provider status when update results differ across providers

When multiple providers are configured (e.g. Claude + Cursor) and a skill's update status differs across providers (one updated, one skipped because of local edits), the output currently only shows the combined result ("updated" wins over "skipped").

Split the output to show per-provider status when there's a collision:
```
Updating tdd (claude) … updated
Updating tdd (cursor) … skipped (modified)
```

When all providers agree, show a single line as today.

Add test coverage for the mixed-provider scenario.
