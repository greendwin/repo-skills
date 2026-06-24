---
id: s13t04
slug: wrap-multi-item-lists-across
status: pending
---

# Wrap multi-item lists across lines in source output

Two single-line comma-joined lists in source output are cramped when they hold many items. Render one item per line instead.

`src/repo_skills/cli/_source.py` · `_dirs_change_line`:
> TODO: multiple dirs in a single line looks ugly, need to split them to
>       multiple lines

`src/repo_skills/config/_source.py` · `_warn_collision`:
> TODO: multiple colliding paths look ugly in a single line, need to split
>       them to multiple lines

Both deferred verbatim from s08t23. Data is complete; only formatting is at issue.

Fix: render the reinit `dirs:` change line and the collision-paths Warning line as multi-line (one dir/path per line) rather than comma-joined single lines. Preserve discovery/stored order (do not sort — first dir is the active write-back target). Remove each TODO once fixed.
