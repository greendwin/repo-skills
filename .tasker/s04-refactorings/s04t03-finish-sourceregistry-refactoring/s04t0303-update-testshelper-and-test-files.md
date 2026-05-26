---
id: s04t0303
slug: update-testshelper-and-test-files
status: done
---

# Update tests/helper and test files

- `tests/cli/helper.py`: rename `FakeGitRepo.path` → `root` to satisfy GitRepo protocol; tighten `install_fake_git` typing; fix imports.
- `tests/test_config.py`: no changes if re-exports are complete; otherwise switch imports.
- Update broken cli test files (test_install, test_merge, test_status, test_source_*, test_provider_*, test_update, test_uninstall) to use re-exported symbols.
- Run `uv run tox` and fix remaining issues.
