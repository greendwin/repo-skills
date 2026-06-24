---
id: s16t04
slug: move-repo-root-source-mapping
status: pending
---

# Move repo-root→source mapping onto SourceRegistry with ambiguity guard

Follow-up refactor from s08t36 (delayed). `_source_for_repo(source_registry, git)` in `src/repo_skills/cli/_merge.py` reverse-maps a repo root back to a registered source by string-comparing `repo_root`; it is used by `_finalize` and `_merge_abort`. Two issues: (1) this is registry knowledge (source identity by location, plus a Path-normalization caveat) leaked into the CLI layer; (2) it returns the *first* registry entry whose `repo_root` matches, silently picking dict order if two sources share a repo root — which for a cross-source `--keep-source` resume could resolve to the wrong source and flip the keep-source gating.

Goal: add `SourceRegistry.source_for_repo_root(root)` owning both directions of the name↔root mapping and the Path caveat; `_merge.py` calls it. When more than one registered source shares `git.root`, raise an ambiguity error (or disambiguate by which source actually contains the skill at `skill.rel_path`) rather than silently picking one. Small, but touches `SourceRegistry`. Cover the multi-source-same-root case with a test.
