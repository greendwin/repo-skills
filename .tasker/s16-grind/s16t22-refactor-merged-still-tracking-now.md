---
id: s16t22
slug: refactor-merged-still-tracking-now
status: pending
---

# Refactor: _merged_still_tracking now has a single caller — thin pass-through layer with _emit_keep_source

## Refactor side-task
- depth: 2
- origin: s16t09 — refactor finding "_merged_still_tracking now has a single caller — thin pass-through layer with _emit_keep_source"

## Goal

Apply the deferred refactoring surfaced while processing s16t09.
- location: src/repo_skills/cli/_merge.py:69-85
- severity: minor

After the uncommitted change, _merged_still_tracking is called from exactly one place: _emit_keep_source (grep confirms its only other usages at lines 163/602/1109 all go through _emit_keep_source). Two adjacent functions now exist where one suffices, and they carry near-duplicate explanatory comments ('content lands in target, manifest left untouched' / 'old_source None ... no tracking suffix'). The split adds an indirection layer without separating responsibilities — _emit_keep_source only adds console.print over the message builder.

## Suggested fix

Collapse into one function, e.g. make _emit_keep_source build and print the message directly (inline the f-string/tracking-suffix logic), or keep _merged_still_tracking as the message builder and drop _emit_keep_source, having the three call sites call console.print(_merged_still_tracking(...)) — but only if a future caller needs the bare string. Given current usage, folding the body of _merged_still_tracking into _emit_keep_source is the cleaner single-responsibility result.
