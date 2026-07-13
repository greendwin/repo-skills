---
id: s06t28
slug: mark-skill-detached-instead-of
status: pending
---

# Mark skill detached instead of error when removed from source

`src/repo_skills/cli/_update.py` · per-skill sync:
> TODO: should we mark this skill as detached instead of reporting an error?

When `source.skills.get(skill_name)` is `None` — the skill no longer exists in the source at all — `update` currently raises `Skill removed from source`. This is distinct from ADR 0002's *unreachable-commit* detach case (there the commit is gone but the skill path still exists in source history); here the skill is gone from the source entirely.

Decide whether to reuse the `detached` manifest flag (preserving the entry + baseline, as ADR 0002 does) for the removed-from-source case, or keep the hard error. Reference `docs/adr/0002-detached-skill-handling.md`. Remove the TODO once resolved.
