---
id: s06t1104
slug: suppress-pyright-warnings-for-unused
status: pending
---

# Suppress Pyright warnings for unused _fake_git fixture params

Multiple tests across `tests/cli/test_update.py` (and likely other test files) accept `_fake_git: FakeGitRepo` as a parameter solely for its side effect (installing the fake git via the fixture). Pyright flags these as "not accessed."

Fix the warnings without breaking the fixture mechanism — e.g. by using `pytest.mark.usefixtures("_fake_git")` on the affected test classes/methods instead of accepting the parameter.
