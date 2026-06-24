---
id: s04t10
slug: derive-source-name-from-register
status: pending
---

# Derive source name from register_source in update-error test fixtures

Test-infra cleanup. The fixture hardcodes the magic source name `"my-project"` in manually-built manifest entries, while `register_source(git_repo)` already establishes the canonical name.

`tests/cli/test_update_errors.py` · `test_skill_removed_from_source_shows_specific_error`:
> TODO: we should use `SourceConfig` from `register_source` instead of
>       hardcoding "my-project" everywhere

Fix at the helper level: have `register_source` (or a helper) surface the registered source's name from `SourceConfig`, and use it instead of the literal `"my-project"` here and in sibling fixtures. Low priority. Remove the TODO once fixed.
