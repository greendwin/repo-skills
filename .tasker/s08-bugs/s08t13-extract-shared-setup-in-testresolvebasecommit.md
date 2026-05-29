---
id: s08t13
slug: extract-shared-setup-in-testresolvebasecommit
status: pending
---

# Extract shared setup in TestResolveBaseCommit

All three tests in `TestResolveBaseCommit` (`tests/cli/test_merge.py`) share an identical 6-line setup block (register_source, create_source_skill, install_skill, save_manifest, write edited file). Extract into a fixture or helper method to reduce duplication. This pattern also appears in other test classes in the file (e.g. `TestBaseCommitSearch`), so the cleanup could be broader.
