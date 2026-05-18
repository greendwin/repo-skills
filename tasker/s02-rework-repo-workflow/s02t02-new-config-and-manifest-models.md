---
id: s02t02
slug: new-config-and-manifest-models
status: pending
---

# New config and manifest models

**Goal:** Replace `Manifest`/`SkillEntry` with the new multi-source, multi-provider structure. Introduce `SourceConfig`, `ProviderConfig`, `SourceRegistry`, and new `Manifest` with per-file hashes. Migrate default paths to XDG (`~/.config/repo-skills/`). No command changes yet — just the data layer.
**Decisions:** XDG config, single global manifest, per-file content hashes, `.repo-skills/source.json`.
**Key files:** `src/repo_skills/manifest.py`, tests
