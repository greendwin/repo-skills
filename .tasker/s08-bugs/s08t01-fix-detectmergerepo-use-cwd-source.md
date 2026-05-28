---
id: s08t01
slug: fix-detectmergerepo-use-cwd-source
status: pending
---

# Fix _detect_merge_repo: use CWD source or scan all sources

_merge.py:574 — Currently picks the first source from manifest. Fix: if CWD is inside a registered source repo and it has a merge branch (active or single), use it (short-circuit). Otherwise scan all registered source repos — single match → use it, multiple → ambiguity error.
