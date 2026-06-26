---
id: s16t28
slug: refactor-plain-prefix-mid-merge
status: pending
---

# Refactor: Plain-prefix mid-merge resume still inlined while keep-prefix resume is extracted

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Plain-prefix mid-merge resume still inlined while keep-prefix resume is extracted"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: tests/cli/test_merge.py:1651, 1686, 2378 (x_git.branch = "skill-merge/claude/tdd")
- severity: nit

The diff extracts _resume_on_keep_branch to centralize the keep-prefixed mid-merge resume (`x_git.branch = "skill-merge-keep/claude/tdd"`), but the parallel plain-prefix resume `x_git.branch = "skill-merge/claude/tdd"` remains hand-written in three places. This is the same 'simulate git leaving the repo mid-merge on branch X' idiom with only the prefix differing, so the abstraction is asymmetric: a reader sees a named helper for keep but a raw assignment for plain, obscuring that they are the same operation.

## Suggested fix

Parameterize the existing helper on prefix rather than hardcoding keep, e.g. `def _resume_on_branch(x_git, branch="skill-merge/claude/tdd")` and have `_resume_on_keep_branch` be a thin call with the keep branch — or fold both into one helper taking a `keep: bool` flag (mirroring _assert_keep_branch_used's *, skill kwarg style). Then the three plain-prefix sites become `_resume_on_branch(x_git)`.
