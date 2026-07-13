---
id: s04t12
slug: cli-code-quality-nits-per
status: pending
---

# CLI code-quality nits (per-provider status, test config, multi-dir line)

Three small, independent cleanups surfaced by TODO triage.

`src/repo_skills/cli/_update.py` · per-provider status printing:
> TODO: we must be able to do this without concatenation

Emit the per-provider status line through a single template instead of `render_template(...) + _STATUS_LABEL[...]` concatenation.

`tests/cli/test_update_errors.py`:
> TODO: we should use `SourceConfig` from `register_source` instead of
> hardcoding "my-project" everywhere

Thread the `SourceConfig` returned by `register_source` into the test instead of hardcoding the `"my-project"` source name.

`src/repo_skills/cli/_source.py` · `_dirs_change_line`:
> TODO: multiple dirs in a single line looks ugly, need to split them to
> multiple lines

Render multiple skills-dirs across multiple lines instead of one crowded line.

Remove each TODO once its cleanup lands.
