---
id: s08t09
slug: add-tests-for-broken-source
status: done
---

# Add tests for broken source display in status output

`_status.py`, tied to:
> TODO: show corresponding source as broken in status list

After s08t06 adds the (broken) label, add test coverage verifying that `SourceBrokenError` results in the source being shown with (broken) styling in `skills status` output.
