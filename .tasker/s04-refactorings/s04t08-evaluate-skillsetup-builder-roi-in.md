---
id: s04t08
slug: evaluate-skillsetup-builder-roi-in
status: pending
---

# Evaluate SkillSetup builder ROI in test helpers

The `SkillSetup` builder in `tests/cli/helper.py` adds ~120 lines of infrastructure (builder class, `_SkillEntry` dataclass, `_register_sources` logic) for marginal test DRY — saving ~5 lines per test at the cost of a new concept every test reader must learn. The old direct setup (`register_source` / `create_source_skill` / `install_skill` / `save_manifest`) was verbose but transparent.

Evaluate whether the builder earns its keep. Options:
- Keep it but document default values at class level so readers don't have to scan `add_skill` kwargs
- Revert to focused per-file helpers like the deleted `_install_two_source_skills`
- Keep as-is if the builder proves its value across enough test files
