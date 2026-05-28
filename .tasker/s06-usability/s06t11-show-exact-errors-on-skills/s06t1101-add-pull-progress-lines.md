---
id: s06t1101
slug: add-pull-progress-lines
status: pending
---

# Add pull progress lines

Replace silent `git.pull()` loop with progress output.

Print `Pulling <source> ... done` after each successful pull.
Print `Pulling <source> ... skipped` when `--offline`.

This is the first visible change — validates the streaming log approach end-to-end.

Tests: assert pull lines appear in output for normal and `--offline` cases.
