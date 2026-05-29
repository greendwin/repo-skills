---
id: s08t06
slug: show-broken-sources-with-broken
status: done
---

# Show broken sources with (broken) label in status output

`_status.py`:
> TODO: show corresponding source as broken in status list

When `get_source` throws `SourceBrokenError`, display the source with a `(broken)` label in status output (same style as `(missing)`) instead of silently showing zero skills. Remove the TODO once fixed.
