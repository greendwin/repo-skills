---
id: s06t12
slug: stream-gitsubprocess-invocations-under-debug
status: done
---

# Stream git/subprocess invocations under --debug

When `--debug` is active, print all git/subprocess command invocations and their output to stderr/console as they happen. Applies to all commands, not just `skills update`.

Discovered during s06t11 design — separated because it's cross-cutting.
