---
id: s06t0801
slug: add-merge-methods-to-gitrepo
status: done
---

# Add merge methods to GitRepo protocol and implementations

**Goal:** Add `merge(branch) -> bool`, `is_merging() -> bool`, `merge_abort() -> None` to the protocol, `RealGitRepo`, and `FakeGitRepo`.

**Decisions:** Three new protocol methods — no `merge_continue` needed since `commit_all` with explicit message handles it.

**Key files:** `src/repo_skills/git.py`, `src/repo_skills/git_real.py`, `tests/cli/helper.py`
