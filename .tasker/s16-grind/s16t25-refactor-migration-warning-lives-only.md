---
id: s16t25
slug: refactor-migration-warning-lives-only
status: pending
---

# Refactor: Migration warning lives only in a code comment, not surfaced to the operator

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "Migration warning lives only in a code comment, not surfaced to the operator"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:48-51 (comment 'deferred keep-source merges ... must be re-run')
- severity: minor

The only record that a behavioral migration is required is an internal comment. A user running `--continue` after upgrade gets no message. This compounds the major finding above and is tracked as s16t17, but worth flagging from the general lens as a correctness/UX gap in the shipped change. Deferred: UX/surfacing gap explicitly scoped to s16t17, not a delivered-path correctness break.

## Suggested fix

Emit a one-line `[yellow]Warning:` on resume when merge-state.json was found and unlinked, e.g. 'Legacy merge state cleared; if this was a deferred --keep-source merge, abort and re-run with --keep-source.'
