---
id: s08t01
slug: fix-detectmergerepo-use-cwd-source
status: done
---

# Fix _detect_merge_repo: use CWD source or scan all sources

`_merge.py` `_detect_merge_repo`:
> TODO: BUG: this is just wrong, it peak first source
> we need to check either '--source' field or cwd()

Currently picks the first source from the manifest. Fix: if CWD is inside a registered source repo and it has a merge branch (active or single), use it (short-circuit). Otherwise scan all registered source repos — single match → use it, multiple → ambiguity error. Remove the TODO once fixed.
