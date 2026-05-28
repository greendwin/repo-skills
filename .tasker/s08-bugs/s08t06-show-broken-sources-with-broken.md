---
id: s08t06
slug: show-broken-sources-with-broken
status: pending
---

# Show broken sources with (broken) label in status output

_status.py:115 — When `get_source` throws `SourceBrokenError`, display the source with a `(broken)` label in status output (same style as `(missing)`) instead of silently showing zero skills.
